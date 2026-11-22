"""End-to-end smoke test on a FRESH, throwaway database (WORKFLOW 9.1).

fresh database -> migrations -> load venue + event -> CROWDSIM run (SYNTHETIC) -> replay through
the real ingestion API (POST /api/crowd/observations, AD-02) -> prediction cycles in event time
-> alerts, then checks the results through the public API.

The real database is never touched: the script creates ``crowdcast_smoke`` in the same Postgres
server, runs every step with DATABASE_URL pointing at it (each tool runs as its own process,
exactly as a user would run it), serves the API on port 8001, and drops the database at the
end (``--keep`` leaves it for inspection). No trained model exists in a fresh database, so the
cycle uses the B0 persistence fallback; the check is that the pipeline works end to end, not
forecast quality.

Usage (from backend/, Postgres running):
  uv run python -m tools.smoke_e2e [--keep]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy.engine import make_url

from crowdcast.common.config import REPO_ROOT, get_settings

SMOKE_DB = "crowdcast_smoke"
PORT = 8001
VENUE = REPO_ROOT / "configs" / "venues" / "v1.yaml"
EVENT = REPO_ROOT / "configs" / "events" / "v1_spring_fest_day1.yaml"
BACKEND = REPO_ROOT / "backend"


def smoke_url(base: str, name: str = SMOKE_DB) -> str:
    """The configured DATABASE_URL with only the database name replaced; refuses any name that
    is not a throwaway smoke database, so the real database can never be dropped."""
    if not name.endswith("_smoke"):
        raise ValueError(f"refusing to use {name!r}: the smoke database name must end in _smoke")
    return make_url(base).set(database=name).render_as_string(hide_password=False)


def admin_dsn(base: str) -> str:
    """libpq DSN of the server's maintenance database (for CREATE / DROP DATABASE)."""
    u = make_url(base)
    return (
        f"host={u.host} port={u.port or 5432} user={u.username} "
        f"password={u.password or ''} dbname=postgres"
    )


def recreate(base: str, drop_only: bool = False) -> None:
    with psycopg.connect(admin_dsn(base), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{SMOKE_DB}" WITH (FORCE)')
        if not drop_only:
            conn.execute(f'CREATE DATABASE "{SMOKE_DB}"')


class Step:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()
        self.rows: list[tuple[str, float, str]] = []

    def run(self, name: str, args: list[str], env: dict[str, str]) -> str:
        t = time.perf_counter()
        p = subprocess.run(
            [sys.executable, *args], cwd=BACKEND, env=env, capture_output=True, text=True
        )
        if p.returncode != 0:
            raise RuntimeError(f"{name} failed ({p.returncode}):\n{p.stdout}\n{p.stderr}")
        last = (p.stdout.strip().splitlines() or [""])[-1]
        self.rows.append((name, time.perf_counter() - t, last))
        print(f"ok   {name:<22} {time.perf_counter() - t:6.1f} s  {last[:110]}")
        return p.stdout


def get(path: str) -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=30) as r:
        return json.loads(r.read())


def wait_for_api(proc: subprocess.Popen[bytes], timeout_s: float = 60) -> None:
    end = time.time() + timeout_s
    while time.time() < end:
        if proc.poll() is not None:
            raise RuntimeError("the API process exited during start-up")
        try:
            get("/api/health")
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.5)
    raise RuntimeError("the API did not answer /api/health in time")


def check(cond: bool, what: str) -> None:
    if not cond:
        raise AssertionError(what)
    print(f"ok   check: {what}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="do not drop the smoke database")
    args = parser.parse_args(argv)
    base = get_settings().database_url
    env = {**os.environ, "DATABASE_URL": smoke_url(base), "PYTHONIOENCODING": "utf-8"}
    steps = Step()
    api: subprocess.Popen[bytes] | None = None
    try:
        recreate(base)
        print(f"ok   fresh database {SMOKE_DB!r}")
        steps.run("migrations", ["-m", "alembic", "upgrade", "head"], env)
        steps.run("load venue", ["-m", "tools.load_config", "venue", str(VENUE)], env)
        out = steps.run("load event", ["-m", "tools.load_config", "event", str(EVENT)], env)
        m = re.search(r"event_id=(\d+)", out)
        check(m is not None, "event loaded and got an id")
        assert m is not None
        event_id = int(m.group(1))
        with tempfile.TemporaryDirectory(prefix="crowdcast_smoke_") as tmp:
            steps.run("CROWDSIM run", ["-m", "tools.crowdsim.run", "--event", str(EVENT),
                                       "--out", tmp], env)  # fmt: skip
            run_dir = next(Path(tmp).glob("regime_*/*"))
            api = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "crowdcast.api.app:app", "--port", str(PORT)],
                cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )  # fmt: skip
            wait_for_api(api)
            print(f"ok   API on port {PORT}")
            steps.run("replay (ingestion API)", ["-m", "tools.crowdsim.replay", str(run_dir),
                      "--event-id", str(event_id), "--api", f"http://127.0.0.1:{PORT}",
                      "--speedup", "0"], env)  # fmt: skip
        steps.run("prediction cycles", ["-m", "tools.run_predictions", "--event-id",
                  str(event_id)], env)  # fmt: skip

        current = get(f"/api/crowd/current/{event_id}")
        check(current["as_of"] is not None, f"current state has data (as of {current['as_of']})")
        check(len(current["zones"]) == 8, "all 8 zones report a count")
        check(
            all(z["data_origin"] == "SYNTHETIC" for z in current["zones"]),
            "every observation is labelled SYNTHETIC",
        )
        pred = get(f"/api/predictions/{event_id}")
        horizons = {f["horizon_min"] for z in pred["zones"] for f in z["forecasts"]}
        check(horizons == {5, 15, 30}, "forecasts exist at 5, 15 and 30 min")
        check(
            all(f["is_fallback"] for z in pred["zones"] for f in z["forecasts"]),
            "no trained model in a fresh database -> persistence fallback",
        )
        alerts = get(f"/api/alerts/{event_id}?limit=500")["alerts"]
        kinds = {a["alert_type"] for a in alerts}
        check(len(alerts) > 0, f"alerts were raised ({len(alerts)}: {sorted(kinds)})")
        check(
            any(a["status"] == "RESOLVED" and a["auto_resolved"] for a in alerts),
            "hysteresis auto-resolved at least one alert",
        )
        print(f"SMOKE TEST PASSED in {time.perf_counter() - steps.t0:.0f} s (event {event_id})")
        return 0
    except (RuntimeError, AssertionError, StopIteration) as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        return 1
    finally:
        if api is not None:
            api.terminate()
            api.wait(timeout=30)
        if not args.keep:
            recreate(base, drop_only=True)
            print(f"dropped {SMOKE_DB!r}")


if __name__ == "__main__":
    sys.exit(main())

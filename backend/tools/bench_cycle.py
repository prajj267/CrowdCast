"""Timing check of the prediction cycle against its budget (WORKFLOW 9.2; doc 07 §5; NFR-PERF-01:
full cycle for <= 15 zones x 3 horizons x 3 quantiles <= 5 s on the reference machine).

Everything runs inside ONE database transaction that is always rolled back, so nothing is
kept: the real cycle code (``forecasting.cycle.run_cycle``: read the 60-min window, shared
FeatureBuilder, active XGBoost model, B0 fallback, write predictions, risk engine + alerts) is
timed for

1. an event already in the database (default: event 32, V1, 8 zones, a full SYNTHETIC replay);
2. the largest venue, V3 (12 zones): venue and one generated event are loaded with the normal
   config loader and its CROWDSIM run is replayed through the real API app
   (``POST /api/crowd/observations``, AD-02), all inside the same rolled-back transaction.

The first cycle of a case includes loading the model files (reported separately); the budget
is checked on the steady-state cycles after the 15-min cold start.

Usage (from backend/, Postgres up, an XGBoost model active, clean tree):
  uv run python -m tools.bench_cycle
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from crowdcast.api.app import app
from crowdcast.api.deps import get_session
from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.forecasting.cycle import COLD_START_MIN, origin_for, run_cycle
from crowdcast.storage.interfaces import get_engine, load_event, load_venue, repository
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config
from tools.crowdsim.replay import replay
from tools.training.train import git_commit

BUDGET_S = 5.0  # NFR-PERF-01
OUT = REPO_ROOT / "runs" / "bench"
V3_EVENT = REPO_ROOT / "data" / "synthetic" / "events" / "v3_e000.yaml"
V3_RUN = REPO_ROOT / "data" / "synthetic" / "crowdsim" / "regime_a" / "v3_e000"


def summary(times: list[float]) -> dict[str, float]:
    a = np.asarray(times)
    return {
        "n": len(times),
        "median_s": float(np.median(a)),
        "p95_s": float(np.percentile(a, 95)),
        "max_s": float(a.max()),
        "mean_s": float(statistics.fmean(times)),
    }


def time_cycles(session: Session, event_id: int, every_min: int) -> dict[str, Any]:
    """Cycles from the first bucket to the last, every ``every_min`` minutes."""
    event = repository.get_event(session, event_id)
    assert event is not None
    first, last = repository.observation_bucket_range(
        session, event_id, origin_for(event.is_synthetic)
    )
    assert first is not None and last is not None, f"event {event_id} has no observations"
    zones = len(repository.list_zones(session, event.venue_id))
    t = first + timedelta(minutes=1)
    cold, warm, fallbacks, first_model_s = [], [], 0, None
    while t <= last + timedelta(minutes=1):
        t0 = time.perf_counter()
        r = run_cycle(session, event_id, t)
        dt = time.perf_counter() - t0
        if r.model_zones and first_model_s is None:
            first_model_s = dt  # includes loading the model files
        elif r.model_zones:
            warm.append(dt)
        else:
            cold.append(dt)
            fallbacks += 1
        t += timedelta(minutes=every_min)
    return {
        "event_id": event_id,
        "zones": zones,
        "first_model_cycle_s": first_model_s,
        "model_cycles": summary(warm),
        "fallback_cycles": len(cold),
        "within_budget": bool(warm) and max(warm) <= BUDGET_S,
    }


def load_v3(session: Session) -> int:
    """V3 venue + event v3_e000 and its replay, inside the caller's transaction."""
    venue_cfg = load_venue_config(REPO_ROOT / "configs" / "venues" / "v3.yaml")
    load_venue(session, venue_cfg)
    event_id = load_event(session, load_event_config(V3_EVENT), venue_cfg).event_id

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:

            def call(path: str, body: dict[str, Any] | None) -> dict[str, Any]:
                r = client.get(path) if body is None else client.post(path, json=body)
                r.raise_for_status()
                out: dict[str, Any] = r.json()
                return out

            totals = replay(V3_RUN, event_id, call, speedup=0)
    finally:
        app.dependency_overrides.clear()
    assert totals["rejected"] == 0, totals
    return event_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", type=int, default=32)
    parser.add_argument("--every", type=int, default=5, help="minutes between timed cycles")
    args = parser.parse_args(argv)
    commit = git_commit()
    if commit.endswith("(dirty working tree)"):
        print("uncommitted changes: commit first (results must come from committed code)")
        return 2

    engine = get_engine()
    with engine.connect() as conn:
        outer = conn.begin()
        try:
            with Session(bind=conn, join_transaction_mode="create_savepoint") as session:
                model = repository.active_model_version(session)
                if model is None or model.model_family != "XGBOOST":
                    print(
                        "no active XGBoost model: activate one first "
                        "(POST /api/models/{id}/activate)"
                    )
                    return 2
                print(f"model {model.model_version_id} {model.name} {model.version}")
                cases = [time_cycles(session, args.event_id, args.every)]
                print(f"V1 done: {json.dumps(cases[-1])}")
                cases.append(time_cycles(session, load_v3(session), args.every))
                print(f"V3 done: {json.dumps(cases[-1])}")
                session.execute(text("SELECT 1"))
        finally:
            outer.rollback()  # nothing from the benchmark is kept

    run = utc_now().strftime("%Y%m%dT%H%M%SZ")
    result = {
        "run": f"cycle_{run}",
        "task": "9.2",
        "git_commit": commit,
        "budget_s": BUDGET_S,
        "model": {"id": model.model_version_id, "name": model.name, "version": model.version},
        "cold_start_min": COLD_START_MIN,
        "data_origin": "SYNTHETIC",
        "machine": "Ryzen 7 8840HS, 31 GB RAM, CPU only (reference machine)",
        "note": "all writes rolled back; V3 loaded and replayed inside the transaction",
        "cases": cases,
        "passed": all(c["within_budget"] for c in cases),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"cycle_{run}.json"
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    for c in cases:
        m = c["model_cycles"]
        print(
            f"event {c['event_id']} ({c['zones']} zones): {m['n']} model cycles, median "
            f"{m['median_s']:.3f} s, p95 {m['p95_s']:.3f} s, max {m['max_s']:.3f} s; first "
            f"(model load) {c['first_model_cycle_s']:.3f} s; budget {BUDGET_S} s -> "
            f"{'OK' if c['within_budget'] else 'OVER'}"
        )
    print(f"{'PASSED' if result['passed'] else 'FAILED'}; written {path}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

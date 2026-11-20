"""Replay a CROWDSIM run into the ingestion API (WORKFLOW 3.4.3; AD-02).

Posts the run's zone-minutes to ``POST /api/crowd/observations`` as SYNTHETIC / SIM_CLEAN, in
event-time order. ``--speedup 60`` sends one simulated minute per real second; ``--speedup 0``
sends as fast as possible (back-fill). Like every other source, the replay goes through the API:
no direct database writes.

Usage (from backend/, API running, event loaded with tools.load_config):
  uv run python -m tools.crowdsim.replay ../data/synthetic/crowdsim/regime_a/v1_spring_fest_day1 \\
      --event-id 32 --speedup 0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd

Poster = Callable[[str, dict[str, Any] | None], dict[str, Any]]  # (path, json body or GET) -> json


def http_poster(base_url: str) -> Poster:
    def call(path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            base_url.rstrip("/") + path,
            data=data,
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result: dict[str, Any] = json.loads(resp.read())
                return result
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{exc.code} {exc.read().decode(errors='replace')}") from exc

    return call


def batches(
    zone_minutes: pd.DataFrame, zone_ids: dict[str, int], event_id: int, minutes_per_batch: int
) -> Iterator[dict[str, Any]]:
    """Request bodies, one per ``minutes_per_batch`` buckets, in time order (≤ 1,000 rows)."""
    zm = zone_minutes.sort_values(["bucket_start", "zone_code"])
    buckets = sorted(zm["bucket_start"].unique())
    for k in range(0, len(buckets), minutes_per_batch):
        chunk = zm[zm["bucket_start"].isin(buckets[k : k + minutes_per_batch])]
        records: list[dict[str, Any]] = chunk.to_dict("records")  # type: ignore[assignment]
        yield {
            "event_id": event_id,
            "data_origin": "SYNTHETIC",
            "source": "crowdsim-replay",
            "observations": [
                {
                    "zone_id": zone_ids[row["zone_code"]],
                    "bucket_start": pd.Timestamp(row["bucket_start"]).isoformat(),
                    "occupancy": int(row["occupancy"]),
                    "inflow": int(row["inflow"]),
                    "outflow": int(row["outflow"]),
                    "mean_speed_mps": round(float(row["mean_speed_mps"]), 3),
                    "quality": "OK",
                    "method": "SIM_CLEAN",
                }
                for row in records
            ],
        }


def replay(
    run_dir: Path,
    event_id: int,
    call: Poster,
    *,
    speedup: float = 0.0,
    minutes_per_batch: int = 1,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    zm = pd.read_parquet(run_dir / "zone_minutes.parquet")
    event = call(f"/api/events/{event_id}", None)
    zones = call(f"/api/venues/{event['venue_id']}/zones", None)["zones"]
    zone_ids = {z["code"]: z["zone_id"] for z in zones}
    missing = sorted(set(zm["zone_code"]) - set(zone_ids))
    if missing:
        raise ValueError(f"run has zones the event's venue lacks: {missing}")
    if minutes_per_batch * len(zone_ids) > 1000:
        raise ValueError("batch would exceed 1,000 rows (doc 14 §5)")

    totals = {"inserted": 0, "updated": 0, "rejected": 0, "requests": 0}
    for body in batches(zm, zone_ids, event_id, minutes_per_batch):
        result = call("/api/crowd/observations", body)
        totals["inserted"] += result["inserted"]
        totals["updated"] += result["updated"]
        totals["rejected"] += len(result["rejected"])
        totals["requests"] += 1
        if speedup > 0:
            sleep(60.0 * minutes_per_batch / speedup)
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--event-id", type=int, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--speedup", type=float, default=60.0, help="0 = as fast as possible")
    parser.add_argument("--minutes-per-batch", type=int, default=1)
    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    totals = replay(
        args.run_dir,
        args.event_id,
        http_poster(args.api),
        speedup=args.speedup,
        minutes_per_batch=args.minutes_per_batch,
    )
    print(f"SYNTHETIC replay done in {time.perf_counter() - t0:.1f} s: {totals}")
    return 0 if totals["rejected"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

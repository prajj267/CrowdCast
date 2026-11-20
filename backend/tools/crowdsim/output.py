"""Write a CROWDSIM run to Parquet + manifest (WORKFLOW 3.3.6; doc 12 §5.2, §6; DESIGN.md §12).

Everything written here is SYNTHETIC and says so in a column and in the manifest.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from crowdcast.common.config import REPO_ROOT
from tools.crowdsim.schedule import SimItem
from tools.crowdsim.sim import SimResult

CROWDSIM_VERSION = "1.0"


def zone_minutes(result: SimResult, event_name: str) -> pd.DataFrame:
    rows = []
    for b, t in enumerate(result.bucket_starts):
        for z, code in enumerate(result.zone_codes):
            rows.append(
                {
                    "event": event_name,
                    "zone_code": code,
                    "bucket_start": t,
                    "occupancy": int(result.occupancy[b, z]),
                    "inflow": int(result.inflow[b, z]),
                    "outflow": int(result.outflow[b, z]),
                    "mean_speed_mps": float(result.mean_speed_mps[b, z]),
                    "data_origin": "SYNTHETIC",
                    "method": "SIM_CLEAN",
                }
            )
    return pd.DataFrame(rows)


def edge_flows(result: SimResult) -> pd.DataFrame:
    rows = [
        {"bucket_start": t, "from_code": a, "to_code": z, "flow": int(result.edge_flow[b, e])}
        for b, t in enumerate(result.bucket_starts)
        for e, (a, z) in enumerate(result.edges)
    ]
    return pd.DataFrame(rows)


def schedule_frame(items: tuple[SimItem, ...], actual: bool) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for it in items:
        row: dict[str, Any] = {
            "title": it.title,
            "category": it.category.value,
            "zone_code": it.zone_code,
            "start": it.start,
            "end": it.end,
            "expected_attendance": it.expected_attendance,
            "attraction_weight": it.attraction_weight,
        }
        if actual:
            row |= {"popularity": it.popularity, "is_popup": it.is_popup}
        rows.append(row)
    return pd.DataFrame(rows)


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return out + (" (dirty working tree)" if dirty else "")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_run(
    result: SimResult,
    out_dir: Path,
    *,
    event_name: str,
    regime: str,
    master_seed: int,
    event_index: int,
    venue_file: Path,
    event_file: Path | None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zone_minutes(result, event_name).to_parquet(out_dir / "zone_minutes.parquet", index=False)
    edge_flows(result).to_parquet(out_dir / "edge_flows.parquet", index=False)
    schedule_frame(result.published, actual=False).to_parquet(
        out_dir / "schedule_published.parquet", index=False
    )
    schedule_frame(result.actual, actual=True).to_parquet(
        out_dir / "schedule_actual.parquet", index=False
    )
    manifest = {
        "data_origin": "SYNTHETIC",
        "note": "CROWDSIM output; all behavioural parameters are placeholders (DESIGN.md)",
        "crowdsim_version": CROWDSIM_VERSION,
        "git_commit": _git_commit(),
        "regime": regime,
        "master_seed": master_seed,
        "event_index": event_index,
        "event_name": event_name,
        "venue_file": venue_file.name,
        "venue_sha256": file_sha256(venue_file),
        "event_file": None if event_file is None else event_file.name,
        "event_sha256": None if event_file is None else file_sha256(event_file),
        "buckets": len(result.bucket_starts),
        "arrivals_total": result.arrivals_total,
        "left_inside_at_stop": result.left_inside_at_stop,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_dir

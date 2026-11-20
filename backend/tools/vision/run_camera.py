"""Run one camera end to end: video -> YOLOX -> ByteTrack -> zone counts -> REAL observations
posted to the ingestion API (WORKFLOW 6.3.3; AD-02: the same contract as every other source).

Frames, boxes and tracks stay in memory; the only outputs are the posted minute aggregates and
a small summary file of those same aggregates under runs/cv/ (doc 19).

Usage (from backend/, API running, event LIVE and not synthetic):
  uv run python -m tools.vision.run_camera --camera CAMERA_YAML --event-id N
  ... --dry-run   (process and print, post nothing)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.venue_graph.interfaces import load_camera_config, load_venue_config
from crowdcast.vision.frames import FrameSource
from crowdcast.vision.interfaces import PersonDetector
from crowdcast.vision.pipeline import process
from crowdcast.vision.tiling import TiledDetector
from crowdcast.vision.yolox_onnx import Preprocessing, YoloxOnnxDetector
from tools.crowdsim.replay import http_poster
from tools.vision.bench_detector import git_commit
from tools.vision.fetch_models import MODEL_DIR, load_manifest

BATCH_MINUTES = 10


def _iso(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=Path, required=True)
    parser.add_argument("--event-id", type=int)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.dry_run and args.event_id is None:
        parser.error("--event-id is required unless --dry-run")

    cam = load_camera_config(args.camera)
    venue = load_venue_config(REPO_ROOT / "configs" / "venues" / f"{cam.camera.venue}.yaml")
    cam.check_against_venue(venue)
    base = YoloxOnnxDetector(
        MODEL_DIR / f"{cam.camera.detector}.onnx",
        preprocessing=Preprocessing(load_manifest()["preprocessing"]),
        score_threshold=0.1,  # ByteTrack needs the low-score detections too (doc 09 §5)
    )
    detector: PersonDetector = (
        TiledDetector(base, tile=base.input_hw[0]) if cam.camera.tiled else base
    )
    frames = FrameSource(
        REPO_ROOT / cam.camera.source, cam.camera.recording_start, cam.camera.sample_fps
    )
    t0 = time.perf_counter()
    rows = process(cam, detector, frames, frames.sample_fps)
    elapsed = time.perf_counter() - t0
    print(
        f"{cam.camera.code}: {len(rows)} zone-minutes from {frames.frame_count} frames "
        f"in {elapsed:.0f} s (REAL, method DETECTION)"
    )
    for r in rows:
        print(
            f"  {r['bucket_start']:%H:%M} {r['zone']}: occupancy {r['occupancy']} "
            f"(raw {r['occupancy_raw']}), in {r['inflow']}, out {r['outflow']}, {r['quality']}"
        )

    totals = {"inserted": 0, "updated": 0, "rejected": 0}
    if not args.dry_run:
        call = http_poster(args.api)
        event = call(f"/api/events/{args.event_id}", None)
        zone_ids = {
            z["code"]: z["zone_id"]
            for z in call(f"/api/venues/{event['venue_id']}/zones", None)["zones"]
        }
        minutes = sorted({_iso(r["bucket_start"]) for r in rows})
        for k in range(0, len(minutes), BATCH_MINUTES):
            chunk = [r for r in rows if _iso(r["bucket_start"]) in minutes[k : k + BATCH_MINUTES]]
            body: dict[str, Any] = {
                "event_id": args.event_id,
                "data_origin": "REAL",
                "source": cam.camera.code,
                "observations": [
                    {
                        **{
                            key: r[key]
                            for key in (
                                "occupancy",
                                "occupancy_raw",
                                "inflow",
                                "outflow",
                                "mean_speed_mps",
                                "quality",
                                "method",
                            )
                        },
                        "zone_id": zone_ids[str(r["zone"])],
                        "bucket_start": _iso(r["bucket_start"]),
                    }
                    for r in chunk
                ],
            }
            result = call("/api/crowd/observations", body)
            totals["inserted"] += result["inserted"]
            totals["updated"] += result["updated"]
            totals["rejected"] += len(result["rejected"])
            for rej in result["rejected"]:
                print(f"  rejected: {rej}")
        print(f"posted: {totals}")

    out = REPO_ROOT / "runs" / "cv" / f"{cam.camera.code}_{utc_now():%Y%m%dT%H%M%SZ}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "camera": cam.camera.code,
                "video": Path(cam.camera.source).name,
                "detector": cam.camera.detector,
                "tiled": cam.camera.tiled,
                "sample_fps": frames.sample_fps,
                "processing_s": round(elapsed, 1),
                "git_commit": git_commit(),
                "data_origin": "REAL",
                "posted": totals,
                "rows": [
                    {
                        **r,
                        "bucket_start": _iso(r["bucket_start"]),
                    }
                    for r in rows
                ],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"summary (aggregates only): {out}")
    return 0 if totals["rejected"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

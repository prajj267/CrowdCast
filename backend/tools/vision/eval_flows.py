"""Flow (line-crossing) error on MOT20 with virtual counting lines (WORKFLOW 7.1.3; doc 16 §2.2).

Ground truth: the annotated tracks (gt.txt, consider-flag 1, class 1) at the full 25 fps, their
foot points run through the SAME debounced CrossingCounter the pipeline uses. Estimate: the
pipeline as deployed - YOLOX-s tiled -> ByteTrack -> CrossingCounter on frames sampled at 5 FPS.
The virtual line runs horizontally across the middle of the image.

Reported: crossings per direction, MAE per 10-s window (the clips are 17 s and 96 s, too short
for minute buckets), net-flow bias, and crossing recall / precision (a detected crossing matches
an unmatched true crossing of the same direction within +-2 s). Recall and false crossings per
minute are the noise-model parameters p_det and r_fp of doc 12 §5.3 (task 7.2.2).

Usage (from backend/):  uv run python -u -m tools.vision.eval_flows
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from crowdcast.aggregation.counting import Crossing, CrossingCounter, LineSpec
from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.vision.tracking import ByteTracker
from tools.vision.bench_detector import git_commit
from tools.vision.eval_counts import PUBLIC, _read, make_detector

FPS = 25
STEP = 5  # pipeline samples 5 FPS
WINDOW_S = 10
MATCH_S = 2.0
T0 = datetime(2000, 1, 1, tzinfo=UTC)  # arbitrary origin: only differences matter


def at(frame: int) -> datetime:
    return T0 + timedelta(seconds=(frame - 1) / FPS)


def gt_tracks(seq_dir: Path) -> dict[int, dict[int, tuple[float, float]]]:
    """frame -> {track id -> foot point} for the evaluated pedestrians."""
    gt = np.loadtxt(seq_dir / "gt" / "gt.txt", delimiter=",")
    gt = gt[(gt[:, 6] == 1) & (gt[:, 7] == 1)]
    out: dict[int, dict[int, tuple[float, float]]] = {}
    for f, tid, x, y, w, h in gt[:, :6]:
        out.setdefault(int(f), {})[int(tid)] = (float(x + w / 2), float(y + h))
    return out


def match(true: list[Crossing], est: list[Crossing]) -> tuple[int, int, int]:
    """(matched, missed true, false estimated) - greedy in time order, same direction, +-2 s."""
    free = list(true)
    matched = 0
    for e in sorted(est, key=lambda c: c.time):
        hit = next(
            (
                t
                for t in free
                if t.direction == e.direction and abs((t.time - e.time).total_seconds()) <= MATCH_S
            ),
            None,
        )
        if hit is not None:
            free.remove(hit)
            matched += 1
    return matched, len(true) - matched, len(est) - matched


def windows(events: list[Crossing], length_s: float) -> np.ndarray:
    """(n_windows, 2) crossings per 10-s window: column 0 direction +1, column 1 direction -1."""
    n = int(np.ceil(length_s / WINDOW_S))
    out = np.zeros((n, 2))
    for e in events:
        k = min(int((e.time - T0).total_seconds() // WINDOW_S), n - 1)
        out[k, 0 if e.direction > 0 else 1] += 1
    return out


def evaluate(seq: str) -> dict[str, Any]:
    seq_dir = PUBLIC / "mot20" / "MOT20" / "train" / f"MOT20-{seq}"
    tracks = gt_tracks(seq_dir)
    last = max(tracks)
    height, width = _read(seq_dir / "img1" / "000001.jpg").shape[:2]
    line = LineSpec((0.0, height / 2), (float(width), height / 2), "below", "above", side_sign=1.0)
    # side_sign +1: positive (= "into below") is the side with larger y for this p1 -> p2

    truth = CrossingCounter([line])
    for f in range(1, last + 1):
        truth.update(at(f), tracks.get(f, {}))

    # as deployed: detections down to 0.1 reach ByteTrack's low-score association (doc 09 §5)
    detector = make_detector("yolox_s", True, score=0.1)
    tracker = ByteTracker()
    estimate = CrossingCounter([line])
    t0 = time.perf_counter()
    for f in range(1, last + 1, STEP):
        det = detector.detect(_read(seq_dir / "img1" / f"{f:06d}.jpg"))
        people = tracker.update(det)
        estimate.update(at(f), {p.track_id: p.foot for p in people})
    seconds = time.perf_counter() - t0

    length_s = last / FPS
    w_true, w_est = windows(truth.events, length_s), windows(estimate.events, length_s)
    matched, missed, false = match(truth.events, estimate.events)
    n_true, n_est = len(truth.events), len(estimate.events)
    net_true = sum(e.direction for e in truth.events)
    net_est = sum(e.direction for e in estimate.events)
    return {
        "sequence": f"MOT20-{seq}",
        "frames": last,
        "length_s": round(length_s, 1),
        "line": "horizontal at mid-height, full width",
        "true_crossings": {
            "down": sum(e.direction > 0 for e in truth.events),
            "up": sum(e.direction < 0 for e in truth.events),
        },
        "est_crossings": {
            "down": sum(e.direction > 0 for e in estimate.events),
            "up": sum(e.direction < 0 for e in estimate.events),
        },
        "window_mae": {
            "down": float(np.mean(np.abs(w_est[:, 0] - w_true[:, 0]))),
            "up": float(np.mean(np.abs(w_est[:, 1] - w_true[:, 1]))),
        },
        "net_flow": {"true": net_true, "estimated": net_est, "bias": net_est - net_true},
        "recall_p_det": matched / n_true if n_true else None,
        "precision": matched / n_est if n_est else None,
        "missed": missed,
        "false_crossings": false,
        "false_per_minute_r_fp": false / (length_s / 60),
        "processing_s": round(seconds, 1),
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    commit = git_commit()  # recorded at the START: later edits cannot change it
    results = []
    for seq in ("01", "03"):
        r = evaluate(seq)
        results.append(r)
        print(json.dumps(r))
    out = REPO_ROOT / "runs" / "cv_eval" / f"flows_{utc_now():%Y%m%dT%H%M%SZ}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "git_commit": commit,
                "data_origin": "REAL (public: MOT20, CC BY-NC-SA 3.0)",
                "pipeline": "YOLOX-s tiled, ByteTrack, CrossingCounter (band 10 px, 10 s), 5 FPS",
                "truth": "gt.txt tracks (consider 1, class 1) at 25 fps through the same counter",
                "match_window_s": MATCH_S,
                "results": results,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

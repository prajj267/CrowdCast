"""Do CPU and DirectML (iGPU) give the same detections? (accelerator check, 2026-11-21)

Runs the same YOLOX model on the same sampled frames on both devices and reports per-frame
count agreement and, for boxes matched by IoU, the largest coordinate and score differences.
A faster device is only usable if it does not change the counts. Writes runs/bench/compare_*.json.

Needs the onnxruntime-directml package (Windows). Usage (from backend/):
  python -m tools.vision.compare_devices --video ../videos/public/shibuya_crossing.webm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.vision.interfaces import Detections, PersonDetector
from crowdcast.vision.tiling import TiledDetector
from crowdcast.vision.yolox_onnx import Preprocessing, YoloxOnnxDetector
from tools.vision.bench_detector import git_commit
from tools.vision.fetch_models import MODEL_DIR, load_manifest


def _iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:  # (N,4) x (M,4) -> (N,M)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return np.asarray(inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9))


def compare(a: Detections, b: Detections) -> tuple[float, float, int]:
    """(max box coordinate diff px, max score diff, unmatched boxes) for IoU >= 0.5 pairs."""
    if len(a) == 0 or len(b) == 0:
        return 0.0, 0.0, abs(len(a) - len(b))
    iou = _iou(a.boxes, b.boxes)
    box_diff, score_diff, matched = 0.0, 0.0, 0
    used: set[int] = set()
    for i in np.argsort(-a.scores):
        j = int(np.argmax(np.where([k in used for k in range(len(b))], -1, iou[i])))
        if iou[i, j] >= 0.5 and j not in used:
            used.add(j)
            matched += 1
            box_diff = max(box_diff, float(np.abs(a.boxes[i] - b.boxes[j]).max()))
            score_diff = max(score_diff, float(abs(a.scores[i] - b.scores[j])))
    return box_diff, score_diff, (len(a) - matched) + (len(b) - matched)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--model", default="yolox_s")
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--tiled", action="store_true")
    args = parser.parse_args(argv)

    prep = Preprocessing(load_manifest()["preprocessing"])
    path = MODEL_DIR / f"{args.model}.onnx"
    cpu_base = YoloxOnnxDetector(path, preprocessing=prep, score_threshold=0.5, device="cpu")
    dml_base = YoloxOnnxDetector(path, preprocessing=prep, score_threshold=0.5, device="dml")
    cpu: PersonDetector = cpu_base
    dml: PersonDetector = dml_base
    if args.tiled:
        cpu = TiledDetector(cpu_base, tile=cpu_base.input_hw[0])
        dml = TiledDetector(dml_base, tile=dml_base.input_hw[0])

    cap = cv2.VideoCapture(str(args.video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    picks = np.linspace(0, max(total - 1, 0), args.frames).astype(int)
    rows = []
    for f in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f))
        ok, frame = cap.read()
        if not ok:
            continue
        img = np.asarray(frame, dtype=np.uint8)
        a, b = cpu.detect(img), dml.detect(img)
        box_d, score_d, unmatched = compare(a, b)
        rows.append(
            {
                "frame": int(f),
                "cpu": len(a),
                "dml": len(b),
                "max_box_diff_px": box_d,
                "max_score_diff": score_d,
                "unmatched": unmatched,
            }
        )
    cap.release()
    same = sum(r["cpu"] == r["dml"] for r in rows)
    summary = {
        "frames": len(rows),
        "count_equal_frames": same,
        "count_abs_diff_total": sum(abs(r["cpu"] - r["dml"]) for r in rows),
        "persons_cpu_total": sum(r["cpu"] for r in rows),
        "max_box_diff_px": max((r["max_box_diff_px"] for r in rows), default=0.0),
        "max_score_diff": max((r["max_score_diff"] for r in rows), default=0.0),
        "unmatched_total": sum(r["unmatched"] for r in rows),
    }
    out = REPO_ROOT / "runs" / "bench" / f"compare_{utc_now():%Y%m%dT%H%M%SZ}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "model": args.model,
                "tiled": args.tiled,
                "score_threshold": 0.5,
                "video": args.video.name,
                "onnxruntime": ort.__version__,
                "providers": {"cpu": cpu_base.providers, "dml": dml_base.providers},
                "git_commit": git_commit(),
                "summary": summary,
                "frames": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"{args.model}{' tiled' if args.tiled else ''}: {summary}")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

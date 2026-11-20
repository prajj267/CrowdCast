"""Task 1.4.1 smoke test: run each YOLOX ONNX model on one image under both input conventions.

The reference image is YOLOX's own assets/dog.jpg (a dog, a bicycle and a truck; no people).
The convention whose detections match the scene with high scores is the one the export expects.
Prints only class counts, scores and boxes - no image is written.

Usage (from backend/):
  uv run python -m tools.vision.smoke_yolox --image ../data/samples/yolox_dog.jpg
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from crowdcast.vision.interfaces import ImageBGR
from crowdcast.vision.yolox_onnx import Preprocessing, YoloxOnnxDetector
from tools.vision.fetch_models import MODEL_DIR

# Indices checked against yolox/data/datasets/coco_classes.py on the YOLOX main branch.
CLASSES = {0: "person", 1: "bicycle", 2: "car", 7: "truck", 16: "dog"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--score", type=float, default=0.3)
    args = parser.parse_args(argv)

    loaded = cv2.imread(str(args.image))
    if loaded is None:
        raise SystemExit(f"cannot read {args.image}")
    image: ImageBGR = np.asarray(loaded, dtype=np.uint8)
    print(f"image {args.image.name}: {image.shape[1]}x{image.shape[0]}")

    for name in ("yolox_nano", "yolox_tiny", "yolox_s"):
        for prep in Preprocessing:
            det = YoloxOnnxDetector(
                MODEL_DIR / f"{name}.onnx", preprocessing=prep, score_threshold=args.score
            )
            det.infer_raw(image)  # warm-up, excluded from timing
            t0 = time.perf_counter()
            det.infer_raw(image)
            ms = (time.perf_counter() - t0) * 1000
            parts = []
            for cid, cname in CLASSES.items():
                d = det.detect_class(image, cid)
                if len(d):
                    box = ", ".join(f"{v:.0f}" for v in d.boxes[0])
                    parts.append(f"{cname} x{len(d)} (top {d.scores[0]:.2f} @ [{box}])")
            found = "; ".join(parts) or "nothing"
            print(f"{name:10s} {det.input_hw[0]}px {prep.value:20s} {ms:6.1f} ms  {found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

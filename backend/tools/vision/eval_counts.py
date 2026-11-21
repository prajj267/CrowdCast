"""Counting accuracy on public datasets, by density band (WORKFLOW 7.1.2; doc 16 §2.1).

Datasets (REAL, public; git-ignored under data/public/, see doc 12 §2):
  mall      2,000 frames 640x480, head points; only heads inside the dataset's ROI mask count,
            so a detection counts when its head point (top-centre, 10 % into the box) is inside.
  sht_b     ShanghaiTech Part B test, 316 images, head points; whole image.
  mot20_01, mot20_03   original-resolution frames sampled at 5 FPS; ground truth = gt.txt rows
            with consider-flag 1 and class 1 (pedestrian), the MOTChallenge evaluation set.

Detector configs: YOLOX-s tiled (pipeline default), YOLOX-s untiled, YOLOX-nano tiled.
A detection counts at score >= 0.5. Writes runs/cv_eval/<run>/{samples.csv,summary.json}.

Usage (from backend/):  uv run python -u -m tools.vision.eval_counts [--datasets mall sht_b ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import scipy.io as sio

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.vision.interfaces import ImageBGR, PersonDetector
from crowdcast.vision.tiling import TiledDetector
from crowdcast.vision.yolox_onnx import Preprocessing, YoloxOnnxDetector
from tools.vision.bench_detector import git_commit
from tools.vision.count_metrics import by_band
from tools.vision.fetch_models import MODEL_DIR, load_manifest

PUBLIC = REPO_ROOT / "data" / "public"
COUNT_SCORE = 0.5
MOT_STEP = 5  # 25 fps -> 5 fps, as in the pipeline (doc 09 §3)
CONFIGS = {
    "yolox_s_tiled": ("yolox_s", True),
    "yolox_s": ("yolox_s", False),
    "yolox_nano_tiled": ("yolox_nano", True),
}

Sample = tuple[str, ImageBGR, int, np.ndarray | None]  # id, image, true count, ROI mask


def _read(path: Path) -> ImageBGR:
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(path)
    return np.asarray(img, dtype=np.uint8)


def mall() -> Iterator[Sample]:
    root = PUBLIC / "mall" / "mall_dataset"
    gt = sio.loadmat(root / "mall_gt.mat")["count"].ravel()
    roi = sio.loadmat(root / "perspective_roi.mat")["roi"][0, 0]["mask"].astype(bool)
    for k, count in enumerate(gt):
        yield f"seq_{k + 1:06d}", _read(root / "frames" / f"seq_{k + 1:06d}.jpg"), int(count), roi


def sht_b() -> Iterator[Sample]:
    root = PUBLIC / "shanghaitech" / "part_B_final" / "test_data"
    for img in sorted((root / "images").glob("*.jpg"), key=lambda p: int(p.stem.split("_")[1])):
        mat = sio.loadmat(root / "ground_truth" / f"GT_{img.stem}.mat")
        number = int(mat["image_info"][0, 0][0, 0]["number"].ravel()[0])
        yield img.stem, _read(img), number, None


def mot20(seq: str) -> Iterator[Sample]:
    root = PUBLIC / "mot20" / "MOT20" / "train" / f"MOT20-{seq}"
    gt = np.loadtxt(root / "gt" / "gt.txt", delimiter=",")
    keep = (gt[:, 6] == 1) & (gt[:, 7] == 1)  # consider-flag 1, class 1 = pedestrian
    counts = np.bincount(gt[keep, 0].astype(int))
    for frame in range(1, int(gt[:, 0].max()) + 1, MOT_STEP):
        true = int(counts[frame]) if frame < len(counts) else 0
        yield f"{frame:06d}", _read(root / "img1" / f"{frame:06d}.jpg"), true, None


def mot20_01() -> Iterator[Sample]:
    return mot20("01")


def mot20_03() -> Iterator[Sample]:
    return mot20("03")


DATASETS: dict[str, Callable[[], Iterator[Sample]]] = {
    "mall": mall,
    "sht_b": sht_b,
    "mot20_01": mot20_01,
    "mot20_03": mot20_03,
}


def count(detector: PersonDetector, image: ImageBGR, roi: np.ndarray | None) -> int:
    det = detector.detect(image)
    boxes = det.boxes[det.scores >= COUNT_SCORE]
    if roi is None:
        return len(boxes)
    hx = ((boxes[:, 0] + boxes[:, 2]) / 2).astype(int).clip(0, roi.shape[1] - 1)
    hy = (boxes[:, 1] + 0.1 * (boxes[:, 3] - boxes[:, 1])).astype(int).clip(0, roi.shape[0] - 1)
    return int(roi[hy, hx].sum())


def make_detector(model: str, tiled: bool, score: float = COUNT_SCORE) -> PersonDetector:
    base = YoloxOnnxDetector(
        MODEL_DIR / f"{model}.onnx",
        preprocessing=Preprocessing(load_manifest()["preprocessing"]),
        score_threshold=score,
    )
    return TiledDetector(base, tile=base.input_hw[0]) if tiled else base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", nargs="*", default=list(DATASETS))
    parser.add_argument("--configs", nargs="*", default=list(CONFIGS))
    args = parser.parse_args(argv)
    commit = git_commit()  # recorded at the START: later edits cannot change it
    run = utc_now().strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "runs" / "cv_eval" / run
    out_dir.mkdir(parents=True, exist_ok=True)
    detectors = {c: make_detector(*CONFIGS[c]) for c in args.configs}
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for ds in args.datasets:
        t0 = time.perf_counter()
        true: list[int] = []
        preds: dict[str, list[int]] = {c: [] for c in args.configs}
        for sid, image, n_true, roi in DATASETS[ds]():
            true.append(n_true)
            row: dict[str, Any] = {"dataset": ds, "sample": sid, "true": n_true}
            for c, det in detectors.items():
                n = count(det, image, roi)
                preds[c].append(n)
                row[c] = n
            rows.append(row)
        summary[ds] = {
            c: {band: vars(m) for band, m in by_band(true, preds[c]).items()} for c in args.configs
        }
        print(f"{ds}: {len(true)} samples in {time.perf_counter() - t0:.0f} s")
        for c in args.configs:
            m = summary[ds][c]["all"]
            print(
                f"  {c:18s} MAE {m['mae']:7.2f}  bias {m['bias']:+8.2f}"
                f"  rel {m['relative_mae']:.3f}  (mean true {m['mean_true']:.1f})"
            )
    with (out_dir / "samples.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "summary.json").write_text(
        json.dumps(
            {
                "run": run,
                "git_commit": commit,
                "data_origin": "REAL (public datasets)",
                "bands": "by TRUE count per image/region (areas not calibrated, doc 16 §2.1)",
                "count_score": COUNT_SCORE,
                "mot20_step": MOT_STEP,
                "results": summary,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"written {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

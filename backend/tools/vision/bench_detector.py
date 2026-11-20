"""Task 1.4.2: CPU speed benchmark of the YOLOX ONNX detectors on a recorded clip.

For each model the clip is decoded in full and frames are sampled at ``--sample-fps`` (doc 09 §3
default: 5 FPS). Per sampled frame we time the detector (letterbox + network + postprocess);
the whole loop including video decoding gives the end-to-end cost per second of video.
The first ``WARMUP`` sampled frames are excluded from the statistics.

"Persons per frame" is descriptive only: it is NOT an accuracy measure (no ground truth here).
No frames, crops or boxes are written - only timing statistics (doc 19).

Usage (from backend/):
  uv run python -m tools.vision.bench_detector --video ../videos/public/shibuya_crossing.webm
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.vision.interfaces import PersonDetector
from crowdcast.vision.tiling import TiledDetector
from crowdcast.vision.yolox_onnx import Preprocessing, YoloxOnnxDetector
from tools.vision.fetch_models import MODEL_DIR, load_manifest, sha256_of

WARMUP = 3
COUNT_SCORE = 0.5  # score used only for the descriptive persons-per-frame figure


@dataclass(frozen=True)
class ModelResult:
    model: str
    input_px: int
    tiled: bool
    runs_per_frame: int  # detector runs per frame (tiles + full-frame pass, or 1)
    frames_timed: int
    detect_ms_median: float
    detect_ms_p90: float
    detect_ms_mean: float
    detector_fps: float  # 1000 / mean detector ms
    wall_s: float  # whole loop incl. decoding of every frame, warm-up included
    video_s: float
    realtime_factor: float  # wall_s / video_s; < 1 means faster than real time
    persons_per_frame_mean: float  # descriptive only, score >= COUNT_SCORE


def sample_step(source_fps: float, target_fps: float) -> int:
    """Process every n-th frame so the sampled rate is as close as possible to ``target_fps``."""
    if source_fps <= 0 or target_fps <= 0:
        raise ValueError("frame rates must be positive")
    return max(1, round(source_fps / target_fps))


def summarize_ms(times_ms: list[float]) -> tuple[float, float, float]:
    """Median, 90th percentile and mean of per-frame times in milliseconds."""
    if not times_ms:
        raise ValueError("no timed frames")
    arr = np.asarray(times_ms, dtype=np.float64)
    return float(np.median(arr)), float(np.percentile(arr, 90)), float(arr.mean())


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "none (no commit yet)"
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.strip()
    return out.stdout.strip() + (" (dirty working tree)" if dirty else "")


def bench_model(
    name: str,
    video: Path,
    step: int,
    preprocessing: Preprocessing,
    threads: int | None,
    tile_overlap: float | None = None,
) -> ModelResult:
    base = YoloxOnnxDetector(
        MODEL_DIR / f"{name}.onnx",
        preprocessing=preprocessing,
        score_threshold=COUNT_SCORE,
        intra_op_threads=threads,
    )
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_hw = (int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
    detector: PersonDetector = base
    runs = 1
    if tile_overlap is not None:
        # Tiles the size of the model input, so each tile is hardly rescaled (see tiling.py).
        tiled = TiledDetector(base, tile=base.input_hw[0], overlap=tile_overlap)
        runs = tiled.runs_per_frame(frame_hw)
        detector = tiled
    times_ms: list[float] = []
    persons: list[int] = []
    index = 0
    sampled = 0
    t_start = time.perf_counter()
    while True:
        if index % step == 0:
            ok, frame = cap.read()
            if not ok:
                break
            t0 = time.perf_counter()
            det = detector.detect(np.asarray(frame, dtype=np.uint8))
            elapsed = (time.perf_counter() - t0) * 1000
            if sampled >= WARMUP:
                times_ms.append(elapsed)
                persons.append(len(det))
            sampled += 1
        elif not cap.grab():  # skipped frames are still decoded, as in the real pipeline
            break
        index += 1
    wall_s = time.perf_counter() - t_start
    cap.release()

    video_s = index / fps
    median, p90, mean = summarize_ms(times_ms)
    return ModelResult(
        model=name,
        input_px=base.input_hw[0],
        tiled=tile_overlap is not None,
        runs_per_frame=runs,
        frames_timed=len(times_ms),
        detect_ms_median=round(median, 2),
        detect_ms_p90=round(p90, 2),
        detect_ms_mean=round(mean, 2),
        detector_fps=round(1000 / mean, 2),
        wall_s=round(wall_s, 2),
        video_s=round(video_s, 2),
        realtime_factor=round(wall_s / video_s, 3),
        persons_per_frame_mean=round(float(np.mean(persons)), 2),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--models", nargs="*", default=["yolox_nano", "yolox_tiny", "yolox_s"])
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--threads", type=int, default=None, help="ORT intra-op threads")
    parser.add_argument(
        "--tiled",
        action="store_true",
        help="also benchmark tiled detection (tiles = model input size, plus a full-frame pass)",
    )
    parser.add_argument("--tile-overlap", type=float, default=0.2)
    parser.add_argument("--task", default="1.4.2", help="WORKFLOW task id recorded in the run")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "runs" / "bench")
    args = parser.parse_args(argv)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open {args.video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    step = sample_step(src_fps, args.sample_fps)

    manifest = load_manifest()
    preprocessing = Preprocessing(manifest["preprocessing"])
    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    config = {
        "task": args.task,
        "video": args.video.name,
        "video_sha256": sha256_of(args.video),
        "video_resolution": f"{width}x{height}",
        "source_fps": round(src_fps, 3),
        "sample_step": step,
        "effective_sample_fps": round(src_fps / step, 3),
        "preprocessing": preprocessing.value,
        "warmup_frames": WARMUP,
        "ort_intra_op_threads": args.threads or "default",
        "tile_overlap": args.tile_overlap if args.tiled else None,
        "model_sha256": {m: manifest["models"][m]["sha256"] for m in args.models},
    }
    environment = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "onnxruntime": ort.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "git_commit": git_commit(),
    }
    print(f"run {run_id}: {args.video.name} {width}x{height} @ {src_fps:.2f} fps, every {step}th")

    variants: list[float | None] = [None, args.tile_overlap] if args.tiled else [None]
    results = []
    for name in args.models:
        for overlap in variants:
            r = bench_model(name, args.video, step, preprocessing, args.threads, overlap)
            results.append(r)
            label = r.model + ("+tiles" if r.tiled else "")
            print(
                f"{label:16s} {r.input_px}px x{r.runs_per_frame:<2d} "
                f"median {r.detect_ms_median:7.1f} ms  p90 {r.detect_ms_p90:7.1f} ms  "
                f"{r.detector_fps:6.1f} FPS  RTF {r.realtime_factor:5.2f}  "
                f"persons/frame {r.persons_per_frame_mean:5.1f}"
            )

    run_dir = args.out / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "config": config,
        "environment": environment,
        "results": [asdict(r) for r in results],
    }
    (run_dir / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"written {run_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

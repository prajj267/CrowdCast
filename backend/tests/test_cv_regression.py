"""Fixed-clip regression test for the CV pipeline (WORKFLOW 6.3.4).

First 25 sampled frames (5 s) of the public Shibuya Crossing clip through the real pipeline
(tiled YOLOX-s -> ByteTrack -> counting). The expected aggregates were recorded once from
committed code (2026-11-21) and are frozen: any change in detection, tracking or counting shows
up here. They are a regression reference, NOT an accuracy result (the clip has no ground truth).
Skipped when the clip or the model weights are not present (both are git-ignored).
"""

from __future__ import annotations

from itertools import islice

import pytest

from crowdcast.common.config import REPO_ROOT
from crowdcast.venue_graph.interfaces import load_camera_config
from crowdcast.vision.frames import FrameSource
from crowdcast.vision.pipeline import process
from crowdcast.vision.tiling import TiledDetector
from crowdcast.vision.yolox_onnx import Preprocessing, YoloxOnnxDetector
from tools.vision.fetch_models import MODEL_DIR, load_manifest

CAMERA = REPO_ROOT / "configs" / "cameras" / "shibuya_cam1.yaml"
EXPECTED = {
    "XN": {"occupancy": 4, "occupancy_raw": 4, "inflow": 1, "outflow": 0, "quality": "PARTIAL"},
    "XS": {"occupancy": 15, "occupancy_raw": 15, "inflow": 0, "outflow": 1, "quality": "PARTIAL"},
}


@pytest.mark.model
def test_first_five_seconds_of_the_clip_give_the_recorded_aggregates() -> None:
    cam = load_camera_config(CAMERA)
    video = REPO_ROOT / cam.camera.source
    model = MODEL_DIR / "yolox_s.onnx"
    if not video.exists() or not model.exists():
        pytest.skip("clip or YOLOX-s weights not present (git-ignored)")
    base = YoloxOnnxDetector(
        model, preprocessing=Preprocessing(load_manifest()["preprocessing"]), score_threshold=0.1
    )
    src = FrameSource(video, cam.camera.recording_start, cam.camera.sample_fps)
    rows = process(cam, TiledDetector(base, tile=base.input_hw[0]), islice(src, 25), src.sample_fps)
    got = {
        str(r["zone"]): {
            k: r[k] for k in ("occupancy", "occupancy_raw", "inflow", "outflow", "quality")
        }
        for r in rows
    }
    assert got == EXPECTED

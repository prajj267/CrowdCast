"""Tests for the YOLOX ONNX detector pipeline (task 1.4.1).

The numpy stages (letterbox, decode, NMS, postprocess) are tested without weights. Tests marked
``model`` load the real ONNX files and are skipped when models/yolox/ has not been fetched.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from crowdcast.vision.interfaces import Detections, PersonDetector
from crowdcast.vision.yolox_onnx import (
    IMAGENET_MEAN,
    IMAGENET_STD,
    PAD_VALUE,
    PERSON_CLASS_ID,
    Preprocessing,
    YoloxOnnxDetector,
    decode,
    letterbox,
    nms,
    postprocess,
)
from tools.vision.fetch_models import MODEL_DIR, load_manifest

INPUT_HW = (64, 64)  # 8x8 + 4x4 + 2x2 = 84 anchor points
N_ANCHORS = 84


def _blue_image(h: int, w: int) -> np.ndarray:
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :, 0] = 255  # BGR: blue channel first
    return img


# ------------------------------------------------------------------ letterbox
def test_letterbox_scales_keeps_aspect_and_pads_bottom_right() -> None:
    x, ratio = letterbox(_blue_image(100, 200), (416, 416), Preprocessing.RAW_BGR)
    assert x.shape == (1, 3, 416, 416)
    assert x.dtype == np.float32
    assert ratio == pytest.approx(2.08)
    content_h = int(100 * ratio)  # 208 rows of image, the rest is padding
    assert np.all(x[0, 0, :content_h, :] == 255)  # blue stays in channel 0 (BGR order)
    assert np.all(x[0, 2, :content_h, :] == 0)
    assert np.all(x[0, :, content_h:, :] == PAD_VALUE)


def test_letterbox_legacy_converts_to_rgb_and_normalises() -> None:
    x, _ = letterbox(_blue_image(100, 200), (416, 416), Preprocessing.LEGACY_RGB_IMAGENET)
    red_of_blue_pixel = (0.0 - IMAGENET_MEAN[0]) / IMAGENET_STD[0]
    blue_of_blue_pixel = (1.0 - IMAGENET_MEAN[2]) / IMAGENET_STD[2]
    assert x[0, 0, 0, 0] == pytest.approx(red_of_blue_pixel)
    assert x[0, 2, 0, 0] == pytest.approx(blue_of_blue_pixel)


# ------------------------------------------------------------------ decode
def test_decode_maps_grid_offsets_to_input_pixels() -> None:
    raw = np.zeros((N_ANCHORS, 85), np.float32)
    out = decode(raw, INPUT_HW)
    # stride 8, row 1, col 2 -> index 1 * 8 + 2; zero offsets put the centre on the cell corner
    assert out[10, :4] == pytest.approx([16, 8, 8, 8])
    # first stride-16 anchor comes after the 64 stride-8 anchors
    assert out[64, :4] == pytest.approx([0, 0, 16, 16])
    # last anchor: stride 32, row 1, col 1
    assert out[83, :4] == pytest.approx([32, 32, 32, 32])


def test_decode_applies_exp_to_size_and_rejects_wrong_anchor_count() -> None:
    raw = np.zeros((N_ANCHORS, 85), np.float32)
    raw[0, 2:4] = np.log(3.0)
    assert decode(raw, INPUT_HW)[0, 2:4] == pytest.approx([24, 24])
    with pytest.raises(ValueError, match="expected 84"):
        decode(np.zeros((80, 85), np.float32), INPUT_HW)


# ------------------------------------------------------------------ nms
def test_nms_suppresses_overlaps_and_orders_by_score() -> None:
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], np.float32)
    scores = np.array([0.6, 0.9, 0.7], np.float32)
    assert nms(boxes, scores, 0.45).tolist() == [1, 2]
    assert nms(boxes, scores, 0.99).tolist() == [1, 2, 0]  # threshold above their IoU (~0.68)


def test_nms_handles_empty_input() -> None:
    assert nms(np.zeros((0, 4), np.float32), np.zeros(0, np.float32), 0.45).size == 0


# ------------------------------------------------------------------ postprocess
def test_postprocess_returns_person_box_in_source_pixels() -> None:
    raw = np.zeros((N_ANCHORS, 85), np.float32)
    raw[10, :4] = [0.5, 0.5, np.log(2.0), np.log(4.0)]  # centre (20, 12), size 16 x 32
    raw[10, 4] = 0.9  # objectness
    raw[10, 5 + PERSON_CLASS_ID] = 0.8
    raw[11, 4], raw[11, 5 + 16] = 0.9, 0.9  # a confident dog must not appear as a person
    det = postprocess(
        raw,
        input_hw=INPUT_HW,
        ratio=0.5,  # source image was twice the input size
        image_hw=(128, 128),
        class_id=PERSON_CLASS_ID,
        score_threshold=0.5,
        nms_iou=0.45,
    )
    assert len(det) == 1
    assert det.scores[0] == pytest.approx(0.72)
    # input box (12, -4, 28, 28) / ratio 0.5 = (24, -8, 56, 56); y1 is clipped to the frame
    assert det.boxes[0] == pytest.approx([24, 0, 56, 56])


def test_postprocess_below_threshold_is_empty() -> None:
    raw = np.zeros((N_ANCHORS, 85), np.float32)
    raw[:, 4], raw[:, 5] = 0.5, 0.5  # every score 0.25
    det = postprocess(
        raw,
        input_hw=INPUT_HW,
        ratio=1.0,
        image_hw=(64, 64),
        class_id=0,
        score_threshold=0.3,
        nms_iou=0.45,
    )
    assert len(det) == 0


def test_detections_validates_shapes() -> None:
    with pytest.raises(ValueError, match=r"\(N, 4\)"):
        Detections(np.zeros((2, 3), np.float32), np.zeros(2, np.float32))
    with pytest.raises(ValueError, match="scores"):
        Detections(np.zeros((2, 4), np.float32), np.zeros(3, np.float32))


# ------------------------------------------------------------------ real model files
def _model_path(name: str) -> Path:
    path = MODEL_DIR / f"{name}.onnx"
    if not path.exists():
        pytest.skip(f"{path} not fetched (uv run python -m tools.vision.fetch_models)")
    return path


@pytest.mark.model
@pytest.mark.parametrize(("name", "size"), [("yolox_nano", 416), ("yolox_s", 640)])
def test_real_model_reads_fixed_input_size_and_finds_no_person_in_blank_frame(
    name: str, size: int
) -> None:
    prep = Preprocessing(load_manifest()["preprocessing"])
    detector = YoloxOnnxDetector(
        _model_path(name),
        preprocessing=prep,
        score_threshold=0.3,
    )
    assert detector.input_hw == (size, size)
    blank = np.full((480, 640, 3), 128, np.uint8)
    as_protocol: PersonDetector = detector
    assert len(as_protocol.detect(blank)) == 0


@pytest.mark.model
def test_default_device_is_cpu_and_missing_directml_is_reported() -> None:
    import onnxruntime as ort

    path = _model_path("yolox_nano")
    prep = Preprocessing(load_manifest()["preprocessing"])
    assert YoloxOnnxDetector(path, preprocessing=prep).providers == ["CPUExecutionProvider"]
    if "DmlExecutionProvider" in ort.get_available_providers():
        pytest.skip("DirectML is installed in this environment")
    with pytest.raises(RuntimeError, match="DirectML requested but not available"):
        YoloxOnnxDetector(path, preprocessing=prep, device="dml")

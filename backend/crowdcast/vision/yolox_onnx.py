"""YOLOX person detector running on the CPU through ONNX Runtime (decision D2, task 1.4.1).

Pipeline, mirroring the official YOLOX ONNX demo (demo/ONNXRuntime/onnx_inference.py):

1. ``letterbox``  - resize keeping aspect ratio, pad bottom/right with grey 114 to the model's
   fixed input size, optionally convert to the legacy RGB + ImageNet normalisation.
2. model          - outputs one row per anchor point: (cx, cy, log w, log h) in grid units,
   objectness and 80 COCO class probabilities (sigmoids already applied inside the export).
3. ``decode``     - turn grid offsets into input-pixel boxes using strides 8, 16, 32.
4. ``postprocess``- score = objectness x class probability, threshold, greedy NMS, undo the
   letterbox scale, clip to the image.

Pure numpy functions are kept separate from the ONNX session so they can be unit-tested
without model weights.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import onnxruntime as ort

from crowdcast.vision.interfaces import Detections, FloatArray, ImageBGR

STRIDES = (8, 16, 32)
PAD_VALUE = 114
PERSON_CLASS_ID = 0  # COCO class index of "person"
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], np.float32)


class Preprocessing(StrEnum):
    """Input convention of an exported YOLOX model (YOLOX changed it after release 0.1.1rc0)."""

    RAW_BGR = "raw_bgr"  # BGR, 0..255, no normalisation (YOLOX main branch)
    LEGACY_RGB_IMAGENET = "legacy_rgb_imagenet"  # RGB, /255, ImageNet mean/std (YOLOX 0.1.x)


def letterbox(
    image_bgr: ImageBGR, input_hw: tuple[int, int], preprocessing: Preprocessing
) -> tuple[FloatArray, float]:
    """Return the (1, 3, H, W) float32 model input and the scale ratio applied to the image."""
    in_h, in_w = input_hw
    h, w = image_bgr.shape[:2]
    ratio = min(in_h / h, in_w / w)
    new_h, new_w = int(h * ratio), int(w * ratio)
    resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    padded = np.full((in_h, in_w, 3), PAD_VALUE, np.uint8)
    padded[:new_h, :new_w] = resized

    x = padded.astype(np.float32)
    if preprocessing is Preprocessing.LEGACY_RGB_IMAGENET:
        x = (x[:, :, ::-1] / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    chw = np.ascontiguousarray(x.transpose(2, 0, 1)[None], dtype=np.float32)
    return chw, ratio


def decode(raw: FloatArray, input_hw: tuple[int, int]) -> FloatArray:
    """Convert raw (A, 5 + C) head outputs to (cx, cy, w, h) in input pixels; scores untouched.

    Anchor points are ordered stride 8, 16, 32, each row-major over its (H/s, W/s) grid.
    """
    in_h, in_w = input_hw
    grids, strides = [], []
    for s in STRIDES:
        gy, gx = np.meshgrid(np.arange(in_h // s), np.arange(in_w // s), indexing="ij")
        grids.append(np.stack((gx, gy), axis=-1).reshape(-1, 2))
        strides.append(np.full((gy.size, 1), s))
    grid = np.concatenate(grids).astype(np.float32)
    stride = np.concatenate(strides).astype(np.float32)
    if grid.shape[0] != raw.shape[0]:
        raise ValueError(f"model output has {raw.shape[0]} rows, expected {grid.shape[0]}")

    out = raw.astype(np.float32, copy=True)
    out[:, :2] = (out[:, :2] + grid) * stride
    out[:, 2:4] = np.exp(out[:, 2:4]) * stride
    return out


def nms(boxes: FloatArray, scores: FloatArray, iou_threshold: float) -> npt.NDArray[np.int64]:
    """Greedy non-maximum suppression. Returns kept indices, highest score first."""
    order = np.argsort(-scores, kind="stable")
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        iw = np.maximum(0.0, np.minimum(x2[i], x2[rest]) - np.maximum(x1[i], x1[rest]))
        ih = np.maximum(0.0, np.minimum(y2[i], y2[rest]) - np.maximum(y1[i], y1[rest]))
        inter = iw * ih
        iou = inter / np.maximum(areas[i] + areas[rest] - inter, 1e-9)
        order = rest[iou <= iou_threshold]
    return np.asarray(keep, dtype=np.int64)


def postprocess(
    raw: FloatArray,
    *,
    input_hw: tuple[int, int],
    ratio: float,
    image_hw: tuple[int, int],
    class_id: int,
    score_threshold: float,
    nms_iou: float,
) -> Detections:
    """Raw head output for one image -> detections of one class in source-image pixels."""
    dec = decode(raw, input_hw)
    scores = dec[:, 4] * dec[:, 5 + class_id]
    mask = scores >= score_threshold
    if not mask.any():
        return Detections.empty()
    cxcywh, scores = dec[mask, :4], scores[mask]
    boxes = np.empty_like(cxcywh)
    boxes[:, :2] = cxcywh[:, :2] - cxcywh[:, 2:] / 2
    boxes[:, 2:] = cxcywh[:, :2] + cxcywh[:, 2:] / 2
    boxes /= ratio
    h, w = image_hw
    # Clip to the frame so foot points (doc 09 §6.1) always lie inside the image.
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h)
    keep = nms(boxes, scores, nms_iou)
    return Detections(boxes[keep].astype(np.float32), scores[keep].astype(np.float32))


class YoloxOnnxDetector:
    """``PersonDetector`` backed by an exported YOLOX ONNX model on the CPU.

    ``score_threshold`` defaults to 0.1 so ByteTrack's low-score association stage
    (doc 09 §5) still receives weak detections; callers counting directly should use 0.5.
    """

    def __init__(
        self,
        model_path: Path,
        *,
        preprocessing: Preprocessing,
        score_threshold: float = 0.1,
        nms_iou: float = 0.45,
        intra_op_threads: int | None = None,
    ) -> None:
        options = ort.SessionOptions()
        if intra_op_threads is not None:
            options.intra_op_num_threads = intra_op_threads
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        model_input = self._session.get_inputs()[0]
        _, _, in_h, in_w = model_input.shape
        if not (isinstance(in_h, int) and isinstance(in_w, int)):
            raise ValueError(f"{model_path}: expected a fixed input size, got {model_input.shape}")
        self._input_name: str = model_input.name
        self.input_hw = (in_h, in_w)
        self.preprocessing = preprocessing
        self.score_threshold = score_threshold
        self.nms_iou = nms_iou

    def infer_raw(self, image_bgr: ImageBGR) -> tuple[FloatArray, float]:
        """Run the network only; returns the (A, 85) raw output and the letterbox ratio."""
        tensor, ratio = letterbox(image_bgr, self.input_hw, self.preprocessing)
        outputs = self._session.run(None, {self._input_name: tensor})
        return np.asarray(outputs[0][0], dtype=np.float32), ratio

    def detect_class(self, image_bgr: ImageBGR, class_id: int) -> Detections:
        raw, ratio = self.infer_raw(image_bgr)
        return postprocess(
            raw,
            input_hw=self.input_hw,
            ratio=ratio,
            image_hw=(image_bgr.shape[0], image_bgr.shape[1]),
            class_id=class_id,
            score_threshold=self.score_threshold,
            nms_iou=self.nms_iou,
        )

    def detect(self, image_bgr: ImageBGR) -> Detections:
        return self.detect_class(image_bgr, PERSON_CLASS_ID)

"""Public interface of the vision module (M2): person detection on single frames.

Other modules depend only on this file. The concrete detector (YOLOX via ONNX Runtime, decision
D2) lives in ``yolox_onnx.py`` and can be swapped without touching callers (doc 09 §11).
Privacy (doc 19): only boxes and scores leave the detector - no crops, embeddings or frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]
ImageBGR = npt.NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class Detections:
    """Person detections for one frame, in source-image pixel coordinates.

    boxes:  (N, 4) float32, columns x1, y1, x2, y2.
    scores: (N,) float32 in [0, 1] (objectness x class probability).
    """

    boxes: FloatArray
    scores: FloatArray

    def __post_init__(self) -> None:
        if self.boxes.ndim != 2 or self.boxes.shape[1] != 4:
            raise ValueError(f"boxes must have shape (N, 4), got {self.boxes.shape}")
        if self.scores.shape != (self.boxes.shape[0],):
            raise ValueError(
                f"scores must have shape ({self.boxes.shape[0]},), got {self.scores.shape}"
            )

    def __len__(self) -> int:
        return int(self.boxes.shape[0])

    @classmethod
    def empty(cls) -> Detections:
        return cls(np.zeros((0, 4), np.float32), np.zeros((0,), np.float32))


class PersonDetector(Protocol):
    """Anything that turns a BGR frame (H, W, 3, uint8) into person detections."""

    def detect(self, image_bgr: ImageBGR) -> Detections: ...

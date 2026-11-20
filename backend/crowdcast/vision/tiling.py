"""Tiled detection for small, distant people (task 1.4.3).

Problem: the YOLOX exports have a fixed input (416 or 640 px), so a 1920x1080 frame is shrunk
about 3-4.6x and distant people become too small to detect.

Method (slicing-aided inference, cf. SAHI; implemented here, no extra dependency):

1. Cover the frame with overlapping tiles of ``tile`` x ``tile`` px (``tile_grid``).
2. Run the wrapped detector on every tile and shift its boxes back to frame coordinates.
3. Drop tile boxes that touch an *inner* tile edge (within ``edge_margin`` px): such a person is
   cut off here, and the overlap guarantees the neighbouring tile sees them whole (as long as
   they are smaller than the overlap). Edges on the frame border are real and keep their boxes.
4. Optionally add one full-frame pass, which catches people larger than the overlap.
5. Merge everything with one NMS so people seen by two tiles are counted once.
"""

from __future__ import annotations

import math

import numpy as np

from crowdcast.vision.interfaces import Detections, FloatArray, ImageBGR, PersonDetector
from crowdcast.vision.yolox_onnx import nms

Tile = tuple[int, int, int, int]  # x0, y0, x1, y1 (x1, y1 exclusive)


def _starts(length: int, tile: int, overlap: float) -> list[int]:
    """Evenly spaced tile starts along one axis; actual overlap >= requested."""
    if length <= tile:
        return [0]
    step = tile * (1.0 - overlap)
    n = math.ceil((length - tile) / step) + 1
    return [round(i * (length - tile) / (n - 1)) for i in range(n)]


def tile_grid(image_hw: tuple[int, int], tile: int, overlap: float) -> list[Tile]:
    """Overlapping tiles covering the whole image, row-major."""
    if tile <= 0 or not 0.0 <= overlap < 1.0:
        raise ValueError("tile must be positive and overlap in [0, 1)")
    h, w = image_hw
    return [
        (x, y, min(x + tile, w), min(y + tile, h))
        for y in _starts(h, tile, overlap)
        for x in _starts(w, tile, overlap)
    ]


def _touches_inner_edge(
    boxes: FloatArray, tile: Tile, image_hw: tuple[int, int], margin: float
) -> np.ndarray:
    """Boolean mask of boxes (tile coordinates) that touch an edge shared with another tile."""
    x0, y0, x1, y1 = tile
    h, w = image_hw
    tw, th = x1 - x0, y1 - y0
    cut = np.zeros(len(boxes), dtype=bool)
    if x0 > 0:
        cut |= boxes[:, 0] <= margin
    if y0 > 0:
        cut |= boxes[:, 1] <= margin
    if x1 < w:
        cut |= boxes[:, 2] >= tw - margin
    if y1 < h:
        cut |= boxes[:, 3] >= th - margin
    return cut


class TiledDetector:
    """``PersonDetector`` that runs another detector on overlapping tiles and merges the boxes."""

    def __init__(
        self,
        base: PersonDetector,
        *,
        tile: int,
        overlap: float = 0.2,
        edge_margin: float = 2.0,
        full_frame_pass: bool = True,
        merge_iou: float = 0.45,
    ) -> None:
        self.base = base
        self.tile = tile
        self.overlap = overlap
        self.edge_margin = edge_margin
        self.full_frame_pass = full_frame_pass
        self.merge_iou = merge_iou

    def runs_per_frame(self, image_hw: tuple[int, int]) -> int:
        return len(tile_grid(image_hw, self.tile, self.overlap)) + int(self.full_frame_pass)

    def detect(self, image_bgr: ImageBGR) -> Detections:
        image_hw = (image_bgr.shape[0], image_bgr.shape[1])
        all_boxes: list[FloatArray] = []
        all_scores: list[FloatArray] = []
        for t in tile_grid(image_hw, self.tile, self.overlap):
            x0, y0, x1, y1 = t
            det = self.base.detect(np.ascontiguousarray(image_bgr[y0:y1, x0:x1]))
            if not len(det):
                continue
            keep = ~_touches_inner_edge(det.boxes, t, image_hw, self.edge_margin)
            shifted = det.boxes[keep] + np.array([x0, y0, x0, y0], np.float32)
            all_boxes.append(shifted)
            all_scores.append(det.scores[keep])
        if self.full_frame_pass:
            full = self.base.detect(image_bgr)
            all_boxes.append(full.boxes)
            all_scores.append(full.scores)
        if not all_boxes:
            return Detections.empty()
        boxes = np.concatenate(all_boxes).astype(np.float32)
        scores = np.concatenate(all_scores).astype(np.float32)
        if not len(boxes):
            return Detections.empty()
        keep_idx = nms(boxes, scores, self.merge_iou)
        return Detections(boxes[keep_idx], scores[keep_idx])

"""Tests for tiled detection (task 1.4.3), using a fake detector with known boxes."""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from crowdcast.vision.interfaces import Detections, ImageBGR
from crowdcast.vision.tiling import TiledDetector, tile_grid


class FakeDetector:
    """Returns the known people boxes clipped to whatever crop it is given.

    A person cut off by the crop edge is returned as the clipped (partial) box, like a real
    detector seeing half a body.
    """

    def __init__(self, people: list[tuple[int, int, int, int]]) -> None:
        self.people = people  # boxes in full-frame coordinates
        self.calls: list[tuple[int, int]] = []

    def detect(self, image_bgr: ImageBGR) -> Detections:
        self.calls.append((image_bgr.shape[0], image_bgr.shape[1]))
        # The crop's top-left pixel encodes its frame position exactly (see _frame()).
        b0, b1, b2 = (int(v) for v in image_bgr[0, 0])
        ox = b0 + 256 * (b1 & 0x0F)
        oy = b2 + 256 * (b1 >> 4)
        h, w = image_bgr.shape[:2]
        boxes = []
        for x1, y1, x2, y2 in self.people:
            cx1, cy1 = max(x1 - ox, 0), max(y1 - oy, 0)
            cx2, cy2 = min(x2 - ox, w), min(y2 - oy, h)
            if cx1 < cx2 and cy1 < cy2:
                boxes.append([cx1, cy1, cx2, cy2])
        if not boxes:
            return Detections.empty()
        arr = np.asarray(boxes, np.float32)
        return Detections(arr, np.full(len(arr), 0.9, np.float32))


def _frame(h: int, w: int) -> ImageBGR:
    """Frame whose pixels encode their own (x, y) exactly (12 bits each), so a crop knows its
    offset: x = B + 256 * (G & 15), y = R + 256 * (G >> 4)."""
    x = np.arange(w)[None, :].repeat(h, 0)
    y = np.arange(h)[:, None].repeat(w, 1)
    img = np.zeros((h, w, 3), np.uint8)
    img[:, :, 0] = x % 256
    img[:, :, 1] = (x // 256) | ((y // 256) << 4)
    img[:, :, 2] = y % 256
    return img


# ------------------------------------------------------------------ grid
def test_grid_covers_image_with_requested_overlap() -> None:
    tiles = tile_grid((1080, 1920), 640, 0.2)
    xs = sorted({t[0] for t in tiles})
    ys = sorted({t[1] for t in tiles})
    assert xs == [0, 427, 853, 1280]
    assert ys == [0, 440]
    assert len(tiles) == 8
    assert max(t[2] for t in tiles) == 1920
    assert max(t[3] for t in tiles) == 1080
    for a, b in pairwise(xs):
        assert 640 - (b - a) >= 0.2 * 640  # actual overlap >= requested


def test_grid_single_tile_when_image_fits() -> None:
    assert tile_grid((300, 400), 640, 0.2) == [(0, 0, 400, 300)]


def test_grid_rejects_bad_parameters() -> None:
    with pytest.raises(ValueError):
        tile_grid((100, 100), 0, 0.2)
    with pytest.raises(ValueError):
        tile_grid((100, 100), 64, 1.0)


# ------------------------------------------------------------------ tiled detection
def test_person_in_overlap_is_counted_once_in_frame_coordinates() -> None:
    # 480 x 960 frame, tiles of 320 with overlap -> person straddling a tile boundary
    person = (300, 100, 340, 180)
    fake = FakeDetector([person])
    tiled = TiledDetector(fake, tile=320, overlap=0.25, full_frame_pass=False)
    det = tiled.detect(_frame(480, 960))
    assert len(det) == 1
    assert det.boxes[0].tolist() == list(map(float, person))


def test_cut_off_partial_box_is_dropped() -> None:
    # Person crosses the right edge of tile 0 (0..320) but lies fully inside tile 1 (213..533)
    person = (300, 100, 340, 180)
    fake = FakeDetector([person])
    tiled = TiledDetector(fake, tile=320, overlap=0.33, full_frame_pass=False)
    det = tiled.detect(_frame(320, 640))
    assert len(det) == 1  # the clipped (300, 100, 320, 180) copy from tile 0 was removed
    assert det.boxes[0].tolist() == list(map(float, person))


def test_person_on_frame_border_is_kept() -> None:
    person = (0, 0, 30, 60)  # touches the image border, not an inner tile edge
    tiled = TiledDetector(FakeDetector([person]), tile=320, overlap=0.25, full_frame_pass=False)
    assert len(tiled.detect(_frame(480, 960))) == 1


def test_full_frame_pass_adds_one_run_and_catches_large_person() -> None:
    big = (100, 50, 600, 470)  # larger than any tile: cut in every tile, all copies dropped
    fake = FakeDetector([big])
    without = TiledDetector(fake, tile=320, overlap=0.25, full_frame_pass=False)
    assert len(without.detect(_frame(480, 960))) == 0
    with_full = TiledDetector(fake, tile=320, overlap=0.25, full_frame_pass=True)
    fake.calls.clear()
    det = with_full.detect(_frame(480, 960))
    assert len(det) == 1
    assert len(fake.calls) == with_full.runs_per_frame((480, 960))
    assert fake.calls[-1] == (480, 960)  # last run is the whole frame

"""Counting, crossings, aggregation and the camera pipeline (WORKFLOW 6.2.3, 6.3; doc 09 §6-7;
doc 17 §2.1). All synthetic: scripted detections on generated frames, no people, no model."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from shapely.geometry import Polygon

from crowdcast.aggregation.counting import (
    CrossingCounter,
    FrameStats,
    LineSpec,
    MinuteAggregator,
    RegionSpec,
    occupancy,
    orient_line,
)
from crowdcast.venue_graph.interfaces import CameraConfig
from crowdcast.vision.frames import Frame
from crowdcast.vision.interfaces import Detections, ImageBGR
from crowdcast.vision.pipeline import process

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
LEFT = RegionSpec("A", [(0, 0), (100, 0), (100, 100), (0, 100)], 1.0)
RIGHT = RegionSpec("B", [(100, 0), (200, 0), (200, 100), (100, 100)], 0.5)
# vertical line at x = 100; B (right) is the entering side
LINE = orient_line(
    (100, 0), (100, 100), "B", "A", {"A": Polygon(LEFT.polygon), "B": Polygon(RIGHT.polygon)}
)


def at(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


# ------------------------------------------------------------------ 6.3.1 occupancy
def test_foot_points_counted_per_region() -> None:
    feet = [(10, 10), (50, 99), (150, 50), (250, 50)]  # last one outside both regions
    assert occupancy(feet, [LEFT, RIGHT]) == {"A": 2, "B": 1}
    assert occupancy([], [LEFT, RIGHT]) == {"A": 0, "B": 0}


def test_line_orientation_follows_the_regions() -> None:
    assert LINE.signed_distance((150, 50)) > 0 and LINE.signed_distance((50, 50)) < 0
    flipped = orient_line((100, 100), (100, 0), "B", "A", {"B": Polygon(RIGHT.polygon)})
    assert flipped.signed_distance((150, 50)) > 0  # same answer whichever way p1/p2 run
    with pytest.raises(ValueError, match="cannot be determined"):
        orient_line((0, 0), (1, 1), "X", "Y", {})


# ------------------------------------------------------------------ 6.3.2 crossings
def walk(counter: CrossingCounter, xs: list[float], t0: float = 0, tid: int = 1) -> None:
    for k, x in enumerate(xs):
        counter.update(at(t0 + k * 0.2), {tid: (x, 50)})


def test_crossing_counts_in_and_out_with_direction() -> None:
    c = CrossingCounter([LINE])
    walk(c, [60, 80, 120, 140])  # A -> B
    walk(c, [160, 120, 80, 60], t0=20)  # B -> A, 20 s later
    assert [e.direction for e in c.events] == [1, -1]
    assert c.flows() == {(T0, "B"): (1, 1), (T0, "A"): (1, 1)}


def test_jitter_inside_the_band_is_not_a_crossing() -> None:
    c = CrossingCounter([LINE])
    walk(c, [80, 95, 105, 96, 104, 97, 80])  # wobbles within +-10 px of the line
    assert c.events == []


def test_stepping_back_within_10_s_cancels() -> None:
    c = CrossingCounter([LINE])
    walk(c, [80, 120, 80])  # in, and straight back out
    assert c.events == []


def test_in_back_in_within_10_s_counts_one_crossing() -> None:
    """In (t=0), back out at t=2 (cancels the first, rule 3), in again at t=3: one crossing."""
    c = CrossingCounter([LINE])
    walk(c, [80, 120])
    walk(c, [80], t0=2)
    walk(c, [120], t0=3)
    assert [e.direction for e in c.events] == [1]


def test_out_then_back_in_within_10_s_cancels_the_out() -> None:
    """In at t=0.2; out at t=15 (counted: > 10 s later); back in at t=18 cancels that out."""
    c = CrossingCounter([LINE])
    walk(c, [80, 120])
    walk(c, [80], t0=15)
    walk(c, [120], t0=18)
    assert [e.direction for e in c.events] == [1]


def test_second_in_crossing_within_10_s_is_ignored() -> None:
    """Rule 2: in, walk around the END of the line back to A (no crossing), in again at t=3."""
    c = CrossingCounter([LINE])
    for k, foot in enumerate([(80, 50), (120, 50), (120, 300), (80, 300), (80, 50), (120, 50)]):
        c.update(at(k * 0.6), {1: foot})
    assert [e.direction for e in c.events] == [1]


def test_crossing_beyond_the_segment_end_is_ignored() -> None:
    c = CrossingCounter([LINE])
    for k, x in enumerate([80, 120]):
        c.update(at(k), {1: (x, 300)})  # passes x = 100 far below the line's end (y 0-100)
    assert c.events == []


# ------------------------------------------------------------------ 6.3.3 aggregation
def test_minute_median_coverage_and_quality() -> None:
    agg = MinuteAggregator([LEFT, RIGHT], sample_fps=5)
    for k in range(300):  # a full minute at 5 FPS
        agg.add(at(k * 0.2), FrameStats({"A": 4 if k % 2 else 6, "B": 3}, 7, [80.0]))
    for k in range(10):  # next minute: only 10 frames
        agg.add(at(60 + k * 0.2), FrameStats({"A": 1, "B": 1}, 2, [80.0]))
    rows = agg.observations({(T0, "B"): (5, 2)})
    first = {r["zone"]: r for r in rows if r["bucket_start"] == T0}
    assert first["A"]["occupancy"] == 5 and first["A"]["quality"] == "OK"  # median of 4/6
    assert first["B"]["occupancy_raw"] == 3 and first["B"]["occupancy"] == 6  # / kappa 0.5
    assert (first["B"]["inflow"], first["B"]["outflow"]) == (5, 2)
    second = [r for r in rows if r["bucket_start"] == T0 + timedelta(minutes=1)]
    assert {r["quality"] for r in second} == {"PARTIAL"}


def test_dense_minute_is_low_confidence() -> None:
    agg = MinuteAggregator([LEFT], sample_fps=5)
    for k in range(300):
        agg.add(at(k * 0.2), FrameStats({"A": 60}, 60, [20.0]))  # many, tiny people
    assert {r["quality"] for r in agg.observations({})} == {"LOW_CONFIDENCE"}


# ------------------------------------------------------------------ pipeline + privacy (6.2.3)
class ScriptedDetector:
    """Two people: one standing in A, one walking from A into B; full score."""

    def __init__(self) -> None:
        self.k = 0

    def detect(self, image_bgr: ImageBGR) -> Detections:
        x = 40 + 2 * self.k  # walker's left edge; foot x = x + 5
        self.k += 1
        boxes = np.array([[20, 40, 30, 90], [x, 40, x + 10, 90]], np.float32)
        return Detections(boxes, np.array([0.9, 0.9], np.float32))


def _camera() -> CameraConfig:
    data: dict[str, Any] = {
        "format_version": 1,
        "camera": {
            "code": "TEST",
            "venue": "v1",
            "source": "videos/none.mp4",
            "recording_start": T0.isoformat(),
            "image_width": 200,
            "image_height": 100,
        },
        "regions": [
            {"zone": "C1", "polygon_px": [[0, 0], [100, 0], [100, 100], [0, 100]]},
            {"zone": "MS", "polygon_px": [[100, 0], [200, 0], [200, 100], [100, 100]]},
        ],
        "lines": [
            {"from": "C1", "to": "MS", "p1": [100, 0], "p2": [100, 100], "positive_side": "MS"}
        ],
    }
    return CameraConfig.model_validate(data)


def test_pipeline_end_to_end_and_writes_nothing(tmp_path: Path) -> None:
    image = np.zeros((100, 200, 3), np.uint8)
    frames = [Frame(i, T0 + timedelta(seconds=i * 0.2), image) for i in range(80)]
    before = set(os.listdir(tmp_path))
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        rows = process(_camera(), ScriptedDetector(), frames, sample_fps=5)
    finally:
        os.chdir(cwd)
    assert set(os.listdir(tmp_path)) == before  # 6.2.3: no frames, crops or tracks on disk
    by_zone = {r["zone"]: r for r in rows}
    assert set(by_zone) == {"C1", "MS"}
    assert (by_zone["MS"]["inflow"], by_zone["C1"]["outflow"]) == (1, 1)  # one A -> B crossing
    assert by_zone["C1"]["method"] == "DETECTION"
    assert set(rows[0]) == {
        "zone",
        "bucket_start",
        "occupancy",
        "occupancy_raw",
        "inflow",
        "outflow",
        "mean_speed_mps",
        "quality",
        "method",
    }


def test_linespec_signed_distance_units() -> None:
    line = LineSpec((0, 0), (0, 10), "B", "A")
    assert line.signed_distance((-3, 5)) == pytest.approx(3)

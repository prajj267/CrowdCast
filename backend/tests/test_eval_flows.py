"""Helpers of the MOT20 flow evaluation (WORKFLOW 7.1.3)."""

from __future__ import annotations

from datetime import timedelta

import numpy as np

from crowdcast.aggregation.counting import Crossing
from tools.vision.eval_flows import T0, at, match, windows


def c(seconds: float, direction: int) -> Crossing:
    return Crossing(T0 + timedelta(seconds=seconds), 0, direction)


def test_frame_time() -> None:
    assert at(1) == T0 and at(26) == T0 + timedelta(seconds=1)


def test_match_same_direction_within_two_seconds() -> None:
    true = [c(1, 1), c(5, 1), c(9, -1)]
    est = [c(2.5, 1), c(9.5, 1), c(20, -1)]  # one hit, wrong direction, too late
    assert match(true, est) == (1, 2, 2)  # matched, missed, false


def test_match_uses_each_true_crossing_once() -> None:
    assert match([c(1, 1)], [c(1, 1), c(1.5, 1)]) == (1, 0, 1)


def test_windows_count_per_direction() -> None:
    w = windows([c(1, 1), c(3, -1), c(12, 1), c(25, 1)], length_s=25)
    np.testing.assert_array_equal(w, [[1, 1], [1, 0], [1, 0]])

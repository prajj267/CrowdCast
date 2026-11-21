"""Split-conformal calibration (WORKFLOW 7.3.3; doc 10 §11)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from crowdcast.forecasting.conformal import (
    apply_offset,
    conformal_offset,
    conformity_scores,
    coverage,
    mean_width,
)
from tools.training.ablation import conformalised


def test_offset_is_the_finite_sample_quantile() -> None:
    scores = np.arange(1, 10, dtype=float)  # n = 9 -> k = ceil(10 * 0.8) = 8
    assert conformal_offset(scores, 0.2) == 8.0
    assert conformal_offset([1.0, 2.0], 0.2) == math.inf  # k = 3 > n
    assert conformal_offset([], 0.2) == math.inf


def test_scores_are_capacity_normalised() -> None:
    q = np.array([[10.0, 20.0, 30.0], [10.0, 20.0, 30.0], [10.0, 20.0, 30.0]])
    actual = np.array([5.0, 20.0, 50.0])
    s = conformity_scores(q, actual, [100.0, 100.0, 10.0])
    np.testing.assert_allclose(s, [0.05, -0.1, 2.0])


def test_apply_offset_widens_narrows_and_keeps_median_inside() -> None:
    q = np.array([[10.0, 20.0, 30.0], [1.0, 2.0, 3.0]])
    wide = apply_offset(q, 0.1, np.array([100.0, 100.0]))
    np.testing.assert_allclose(wide, [[0.0, 20.0, 40.0], [0.0, 2.0, 13.0]])  # floored at 0
    narrow = apply_offset(q, -0.2, np.array([100.0, 100.0]))
    np.testing.assert_allclose(narrow, [[20.0, 20.0, 20.0], [2.0, 2.0, 2.0]])  # P50 kept inside
    assert mean_width(wide) > mean_width(q) > mean_width(narrow)


def test_calibration_restores_nominal_coverage_on_exchangeable_data() -> None:
    rng = np.random.default_rng(3)
    n = 20_000
    actual = rng.normal(100, 10, n)
    q = np.column_stack([np.full(n, 95.0), np.full(n, 100.0), np.full(n, 105.0)])  # too narrow
    cap = np.full(n, 100.0)
    calib, test = slice(0, n // 2), slice(n // 2, n)
    assert coverage(q[test], actual[test]) < 0.5
    off = conformal_offset(conformity_scores(q[calib], actual[calib], cap[calib]))
    assert coverage(apply_offset(q[test], off, cap[test]), actual[test]) == pytest.approx(
        0.8, abs=0.02
    )


def test_validation_split_is_cross_calibrated_by_event() -> None:
    # event "a" intervals are perfect, event "b" intervals miss: with cross-calibration the
    # offset applied to "a" comes only from "b" (and vice versa)
    rows = pd.DataFrame(
        {
            "event_id": ["a"] * 10 + ["b"] * 10,
            "n_t": 0.0,
            "y": [0.5] * 10 + [0.9] * 10,
            "capacity_abs": 100.0,
        }
    )
    q = np.tile([40.0, 50.0, 60.0], (20, 1))
    out = conformalised(rows, q)
    # "b" misses by 30 persons (0.3 of capacity) -> "a" is widened by 30; "a" fits with score
    # -0.1 -> "b" is narrowed by 10
    np.testing.assert_allclose(out[0], [10.0, 50.0, 90.0])
    np.testing.assert_allclose(out[10], [50.0, 50.0, 50.0])

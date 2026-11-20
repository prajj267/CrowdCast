"""Baselines B0-B3 against hand-computed values (WORKFLOW 4.1.2; doc 10 §2, §3.2)."""

from __future__ import annotations

import numpy as np
import pytest

from crowdcast.forecasting.baselines import (
    all_baselines,
    b0_persistence,
    b1_moving_average,
    b2_linear_trend,
    b3_conservation,
    forward_fill,
)

NAN = float("nan")
# One zone rising by exactly 2 per minute: 10, 12, ..., 30 (11 minutes, issue time = last row).
RAMP = np.arange(10, 31, 2, dtype=float)


def test_b0_persistence() -> None:
    assert b0_persistence(RAMP, 5).tolist() == [30.0]
    assert b0_persistence(RAMP, 30).tolist() == [30.0]


def test_b1_moving_average_of_last_five() -> None:
    # (22 + 24 + 26 + 28 + 30) / 5 = 26
    assert b1_moving_average(RAMP, 15).tolist() == [26.0]
    # short history: mean of what exists, (10 + 12) / 2
    assert b1_moving_average([10, 12], 5).tolist() == [11.0]


def test_b2_linear_trend() -> None:
    # slope over the last 10 minutes is exactly 2 -> 30 + 2h
    assert b2_linear_trend(RAMP, 5).tolist() == pytest.approx([40.0])
    assert b2_linear_trend(RAMP, 30).tolist() == pytest.approx([90.0])
    # hand OLS on (0,1), (1,5), (2,3): x_bar = 1, y_bar = 3, slope = ((-1)(-2) + 0 + (1)(0)) / 2 = 1
    assert b2_linear_trend([1, 5, 3], 10).tolist() == pytest.approx([13.0])
    # a single point has no slope; B2 is not clipped, so a falling trend may go below 0
    assert b2_linear_trend([7], 15).tolist() == [7.0]
    assert b2_linear_trend([20, 10], 5).tolist() == pytest.approx([-40.0])


def test_b3_conservation_uses_recent_net_flow_and_clips() -> None:
    fin = np.full(11, 5.0)
    fout = np.full(11, 3.0)  # net +2 per minute
    assert b3_conservation(RAMP, fin, fout, capacity=[100], h=5).tolist() == [40.0]
    # cap: 1.5 * C = 45 < 30 + 2 * 30
    assert b3_conservation(RAMP, fin, fout, capacity=[30], h=30).tolist() == [45.0]
    # net outflow cannot push occupancy below 0
    assert b3_conservation(RAMP, fout, fin, capacity=[100], h=30).tolist() == [0.0]


def test_b3_uses_only_the_last_k_minutes() -> None:
    fin = [100, 100, 100, 0, 0, 0, 0, 0]  # old surge must not count
    fout = [0, 0, 0, 0, 0, 0, 0, 10]  # last 5 minutes: net 0, 0, 0, 0, -10 -> mean -2
    n = [50] * 8
    assert b3_conservation(n, fin, fout, capacity=[100], h=5).tolist() == [40.0]


def test_b3_skips_missing_flows() -> None:
    fin = [4, NAN, 4, 4, 4]
    fout = [0, 0, 0, 0, 0]
    assert b3_conservation([10] * 5, fin, fout, capacity=[100], h=5).tolist() == [30.0]
    # no usable flow at all -> persistence
    assert b3_conservation([10] * 5, [NAN] * 5, [0] * 5, capacity=[100], h=5).tolist() == [10.0]


def test_missing_occupancy_is_forward_filled_only() -> None:
    hist = np.array([[NAN, 1.0], [5.0, NAN], [NAN, NAN]])
    np.testing.assert_array_equal(forward_fill(hist), [[NAN, 1.0], [5.0, 1.0], [5.0, 1.0]])
    # a zone with no value yet stays unknown (no back-fill from the future)
    assert np.isnan(b0_persistence([[NAN], [NAN]], 5)[0])


def test_vectorised_over_zones_and_horizons() -> None:
    n = np.column_stack([RAMP, np.full(11, 7.0)])
    flows = np.zeros((11, 2))
    out = all_baselines(n, flows + 1, flows, capacity=[100, 100])
    assert set(out) == {"B0", "B1", "B2", "B3"}
    assert all(v.shape == (3, 2) for v in out.values())
    np.testing.assert_allclose(out["B2"][:, 0], [40, 60, 90])  # zone 0: 30 + 2h
    np.testing.assert_allclose(out["B2"][:, 1], [7, 7, 7])  # zone 1: flat
    np.testing.assert_allclose(out["B3"][:, 1], [12, 22, 37])  # 7 + h * 1


def test_rejects_empty_history() -> None:
    with pytest.raises(ValueError):
        b0_persistence(np.empty((0, 2)), 5)

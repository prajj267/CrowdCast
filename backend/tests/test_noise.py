"""Noise model (WORKFLOW 7.2.2; doc 12 §5.3)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tools.crowdsim.make_noisy import noisy_zone_minutes
from tools.crowdsim.noise import (
    M_CAP,
    PLACEHOLDER,
    NoiseParams,
    calibrate_occupancy,
    noisy_edge_flows,
    noisy_occupancy,
)


def test_calibration_recovers_a_known_linear_undercount() -> None:
    # miss fraction exactly 0.1 + 0.1 * rho at the band densities 0.25 / 1.0 / 2.25 / 3.5
    true = [8] * 10 + [20] * 10 + [50] * 10 + [100] * 10
    miss = {8: 0.125, 20: 0.2, 50: 0.325, 100: 0.45}
    pred = [t * (1 - miss[t]) for t in true]
    m0, m1, sigma = calibrate_occupancy(true, pred)
    assert m0 == pytest.approx(0.1) and m1 == pytest.approx(0.1)
    assert sigma == pytest.approx(0.0, abs=1e-9)


def test_calibration_clips_to_valid_ranges() -> None:
    m0, m1, _ = calibrate_occupancy([5, 50, 100], [10, 80, 150])  # overcounting
    assert 0 <= m0 <= M_CAP and m1 >= 0


def test_noisy_occupancy_undercounts_dense_zones_more() -> None:
    p = NoiseParams(0.05, 0.1, 0.0, 1.0, 0.0, "test")
    n = np.array([[100.0, 100.0]])
    area = np.array([1000.0, 25.0])  # rho 0.1 vs 4.0
    out = noisy_occupancy(n, area, p, np.random.default_rng(0))
    assert out[0, 0] == round(100 * (1 - 0.06)) and out[0, 1] == round(100 * (1 - 0.45))
    dense = noisy_occupancy(np.array([[1000.0]]), np.array([10.0]), p, np.random.default_rng(0))
    assert dense[0, 0] == round(1000 * (1 - M_CAP))  # capped at 0.6


def test_noisy_flows_thin_and_add_false_crossings() -> None:
    rng = np.random.default_rng(1)
    flows = np.full((20000, 1), 10.0)
    out = noisy_edge_flows(flows, NoiseParams(0, 0, 0, 0.8, 0.5, "test"), rng)
    assert out.mean() == pytest.approx(10 * 0.8 + 0.5, rel=0.02)
    assert (out >= 0).all()


def test_placeholders_are_labelled() -> None:
    assert "placeholder" in PLACEHOLDER.source


def _clean_run() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two zones, three minutes; OUTSIDE -> A -> B with fixed flows."""
    t = pd.date_range("2027-01-01 10:00", periods=3, freq="min", tz="UTC")
    zm = pd.DataFrame(
        {
            "event": "x",
            "zone_code": ["A", "B"] * 3,
            "bucket_start": np.repeat(t, 2),
            "occupancy": [10, 0, 15, 5, 20, 10],
            "inflow": [10, 0, 10, 5, 10, 5],
            "outflow": [0, 0, 5, 0, 5, 0],
            "mean_speed_mps": 1.3,
            "data_origin": "SYNTHETIC",
            "method": "SIM_CLEAN",
        }
    )
    ef = pd.DataFrame(
        {
            "bucket_start": np.repeat(t, 2),
            "from_code": ["OUTSIDE", "A"] * 3,
            "to_code": ["A", "B"] * 3,
            "flow": [10, 0, 10, 5, 10, 5],
        }
    )
    return zm, ef


def test_noisy_zone_minutes_keeps_rows_and_marks_method() -> None:
    zm, ef = _clean_run()
    params = NoiseParams(0.2, 0.0, 0.1, 0.7, 0.0, "test")
    out = noisy_zone_minutes(zm, ef, {"A": 100.0, "B": 100.0}, params, np.random.default_rng(1))
    assert len(out) == len(zm)
    assert list(out.columns) == list(zm.columns)
    assert set(out["method"]) == {"SIM_NOISY"} and set(out["data_origin"]) == {"SYNTHETIC"}
    assert out["mean_speed_mps"].isna().all()
    assert (out[["occupancy", "inflow", "outflow"]] >= 0).all().all()
    # crossings are thinned: observed flows never exceed the true ones without false positives
    merged = out.merge(zm, on=["bucket_start", "zone_code"], suffixes=("", "_true"))
    assert (merged["inflow"] <= merged["inflow_true"]).all()
    # the A->B crossing is counted once as A's outflow and once as B's inflow
    a = out[out["zone_code"] == "A"].set_index("bucket_start")["outflow"]
    b = out[out["zone_code"] == "B"].set_index("bucket_start")["inflow"]
    pd.testing.assert_series_equal(a, b, check_names=False)


def test_noisy_zone_minutes_is_reproducible_per_seed() -> None:
    zm, ef = _clean_run()
    area = {"A": 50.0, "B": 50.0}
    one = noisy_zone_minutes(zm, ef, area, PLACEHOLDER, np.random.default_rng(7))
    two = noisy_zone_minutes(zm, ef, area, PLACEHOLDER, np.random.default_rng(7))
    pd.testing.assert_frame_equal(one, two)

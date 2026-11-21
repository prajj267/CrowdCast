"""Noise model (WORKFLOW 7.2.2; doc 12 §5.3)."""

from __future__ import annotations

import numpy as np
import pytest

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

"""Timing summary of the cycle benchmark (WORKFLOW 9.2)."""

from __future__ import annotations

import pytest

from tools.bench_cycle import summary


def test_summary_statistics() -> None:
    s = summary([0.1, 0.2, 0.3, 0.4, 2.0])
    assert s["n"] == 5
    assert s["median_s"] == pytest.approx(0.3)
    assert s["max_s"] == pytest.approx(2.0)
    assert s["mean_s"] == pytest.approx(0.6)
    assert 0.4 < s["p95_s"] <= 2.0

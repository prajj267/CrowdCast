"""Tests for the pure helpers of the detector benchmark (task 1.4.2)."""

from __future__ import annotations

import pytest

from tools.vision.bench_detector import sample_step, summarize_ms


@pytest.mark.parametrize(
    ("source", "target", "step"),
    [(25.0, 5.0, 5), (29.97, 5.0, 6), (30.0, 5.0, 6), (60.0, 5.0, 12), (4.0, 5.0, 1)],
)
def test_sample_step_matches_target_rate(source: float, target: float, step: int) -> None:
    assert sample_step(source, target) == step


def test_sample_step_rejects_non_positive_rates() -> None:
    with pytest.raises(ValueError):
        sample_step(0.0, 5.0)


def test_summarize_ms() -> None:
    median, p90, mean = summarize_ms([10.0, 20.0, 30.0, 40.0, 100.0])
    assert median == 30.0
    assert p90 == pytest.approx(76.0)  # linear interpolation between 40 and 100
    assert mean == 40.0
    with pytest.raises(ValueError):
        summarize_ms([])

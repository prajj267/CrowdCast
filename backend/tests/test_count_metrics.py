"""Counting metrics, hand-checked (WORKFLOW 7.1.2; doc 16 §2.1)."""

from __future__ import annotations

import math

import pytest

from tools.vision.count_metrics import band_of, by_band, count_metrics


def test_bands_follow_doc_16() -> None:
    assert [band_of(c) for c in (0, 10, 11, 30, 31, 60, 61, 500)] == [
        "0-10",
        "0-10",
        "11-30",
        "11-30",
        "31-60",
        "31-60",
        ">60",
        ">60",
    ]
    with pytest.raises(ValueError):
        band_of(-1)


def test_metrics_by_hand() -> None:
    # errors: -2, 0, +4 -> MAE 2, RMSE sqrt(20/3), bias 2/3, relative 6 / 30
    m = count_metrics([10, 10, 10], [8, 10, 14])
    assert (m.n, m.mae, m.mean_true) == (3, 2.0, 10.0)
    assert m.bias == pytest.approx(2 / 3)
    assert m.rmse == pytest.approx(math.sqrt(20 / 3))
    assert m.relative_mae == pytest.approx(0.2)


def test_undercount_has_negative_bias() -> None:
    assert count_metrics([50, 70], [30, 40]).bias == -25.0


def test_by_band_splits_on_the_true_count() -> None:
    out = by_band([5, 20, 25, 100], [5, 10, 25, 50])
    assert set(out) == {"all", "0-10", "11-30", ">60"}
    assert out["11-30"].n == 2 and out["11-30"].mae == 5.0
    assert out[">60"].bias == -50.0


def test_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        count_metrics([], [])
    with pytest.raises(ValueError):
        count_metrics([1, 2], [1])

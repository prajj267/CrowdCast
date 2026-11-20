"""XGBoost quantile wrapper (WORKFLOW 5.3.1; doc 10 §6)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from crowdcast.forecasting.xgb import (
    QuantileForecaster,
    artifacts_complete,
    load_model,
    predict_change,
    save_model,
    to_occupancy,
    train_booster,
)


def test_inverse_transform_floors_at_zero_and_sorts_quantiles() -> None:
    change = np.array([[0.2, -0.1, 0.05], [-0.9, -0.5, -0.2]])  # first row: crossed quantiles
    out = to_occupancy([100, 50], [100, 100], change)
    np.testing.assert_allclose(out[0], [90, 105, 120])  # 100 + 100 * y, then sorted
    np.testing.assert_allclose(out[1], [0, 0, 30])  # negatives floored at 0, then sorted
    assert np.all(np.diff(out, axis=1) >= 0)


def _toy(n: int, seed: int) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = pd.DataFrame({"a": rng.uniform(0, 1, n), "b": rng.uniform(0, 1, n)})
    y = 0.5 * x["a"].to_numpy() + rng.normal(0, 0.05, n)
    return x, y


def test_quantile_model_orders_quantiles_and_round_trips(tmp_path: Path) -> None:
    xt, yt = _toy(2000, 0)
    xv, yv = _toy(300, 1)
    booster = train_booster(xt, yt, xv, yv, seed=2027, params={"max_depth": 3})
    change = predict_change(booster, xv)
    assert change.shape == (300, 3)
    # the 0.1 quantile is below the 0.9 quantile on (almost) every row before sorting
    assert np.mean(change[:, 0] <= change[:, 2]) > 0.95
    manifest = {
        "horizons": [5], "best_iteration": {"5": int(booster.best_iteration)},
        "feature_set": "A1", "feature_columns": ["a", "b"],
    }  # fmt: skip
    save_model(tmp_path / "m", {5: booster}, manifest)
    assert artifacts_complete(tmp_path / "m") == []
    loaded = load_model(tmp_path / "m")
    assert isinstance(loaded, QuantileForecaster)
    np.testing.assert_allclose(predict_change(loaded.boosters[5], xv), change, rtol=1e-6)


def test_missing_artifacts_are_reported(tmp_path: Path) -> None:
    assert artifacts_complete(tmp_path) == ["manifest.json"]
    (tmp_path / "manifest.json").write_text('{"horizons": [5, 15]}', encoding="utf-8")
    (tmp_path / "h5.json").write_text("{}", encoding="utf-8")
    assert artifacts_complete(tmp_path) == ["h15.json"]

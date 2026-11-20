"""XGBoost quantile forecaster (doc 10 §1.3, §6, §11; WORKFLOW 5.3.1).

Direct multi-horizon strategy: one booster per horizon, each predicting the 0.1/0.5/0.9
quantiles of the capacity-normalised change y = (N(t+h) - N(t)) / C with XGBoost's quantile
loss. Predictions are mapped back with N = max(0, N(t) + C * y) and the three quantiles are
SORTED after that inverse transform, so they can never cross (doc 10 §6, FR-FC-02).

A trained model is a directory: ``h5.json``, ``h15.json``, ``h30.json`` + ``manifest.json``
(feature set, feature columns, outflow shares per venue, data hash, seed, git commit, metrics).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
import xgboost as xgb

from crowdcast.forecasting.features import Arr, FeatureSet

QUANTILES = (0.1, 0.5, 0.9)

# Defaults before tuning (Optuna in Phase 7, doc 10 §8.3) - placeholders, labelled as such.
DEFAULT_PARAMS: dict[str, Any] = {
    "objective": "reg:quantileerror",
    "quantile_alpha": list(QUANTILES),
    "tree_method": "hist",
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
}
NUM_BOOST_ROUND = 2000
EARLY_STOPPING_ROUNDS = 50


def train_booster(
    x_train: pd.DataFrame,
    y_train: npt.ArrayLike,
    x_val: pd.DataFrame,
    y_val: npt.ArrayLike,
    *,
    seed: int,
    params: dict[str, Any] | None = None,
) -> xgb.Booster:
    """Fit one horizon's quantile booster; early stopping on the validation pinball loss."""
    p = {**DEFAULT_PARAMS, **(params or {}), "seed": seed}
    dtrain = xgb.DMatrix(x_train, label=np.asarray(y_train))
    dval = xgb.DMatrix(x_val, label=np.asarray(y_val))
    return xgb.train(
        p,
        dtrain,
        num_boost_round=NUM_BOOST_ROUND,
        evals=[(dval, "validation")],
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        verbose_eval=False,
    )


def predict_change(booster: xgb.Booster, x: pd.DataFrame) -> Arr:
    """(rows, 3) predicted normalised change for the 0.1/0.5/0.9 quantiles."""
    best = booster.best_iteration if booster.best_iteration is not None else 0
    out = booster.predict(xgb.DMatrix(x), iteration_range=(0, best + 1))
    return np.asarray(out, dtype=np.float64).reshape(len(x), len(QUANTILES))


def to_occupancy(n_now: npt.ArrayLike, capacity: npt.ArrayLike, change: Arr) -> Arr:
    """Inverse transform, floor at 0, then sort the quantiles (no crossing)."""
    n = np.asarray(n_now, dtype=np.float64)[:, None]
    c = np.asarray(capacity, dtype=np.float64)[:, None]
    occupancy = np.maximum(0.0, n + c * change)
    return np.sort(occupancy, axis=1)


@dataclass
class QuantileForecaster:
    """A loaded model directory."""

    path: Path
    manifest: dict[str, Any]
    boosters: dict[int, xgb.Booster]

    @property
    def feature_set(self) -> FeatureSet:
        return FeatureSet(self.manifest["feature_set"])

    @property
    def columns(self) -> list[str]:
        cols: list[str] = self.manifest["feature_columns"]
        return cols

    def outflow_share(self, venue_name: str, codes: tuple[str, ...]) -> Arr | None:
        """Training-estimated shares for this venue, reordered to ``codes``; None if unknown."""
        entry = self.manifest.get("outflow_shares", {}).get(venue_name)
        if entry is None or set(entry["codes"]) != set(codes):
            return None
        pos = [entry["codes"].index(c) for c in codes]
        m = np.asarray(entry["matrix"], dtype=np.float64)
        return np.asarray(m[np.ix_(pos, pos)], dtype=np.float64)

    def predict(self, rows: pd.DataFrame, horizon: int, capacity: Arr) -> Arr:
        """(rows, 3) occupancy quantiles for feature ``rows`` built at ``horizon``."""
        change = predict_change(self.boosters[horizon], rows[self.columns])
        zone = rows["zone"].to_numpy()
        return to_occupancy(rows["n_t"].to_numpy(), capacity[zone], change)


def save_model(path: Path, boosters: dict[int, xgb.Booster], manifest: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for h, b in boosters.items():
        b.save_model(path / f"h{h}.json")
    (path / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def load_model(path: Path) -> QuantileForecaster:
    manifest: dict[str, Any] = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    boosters: dict[int, xgb.Booster] = {}
    for h in manifest["horizons"]:
        b = xgb.Booster()
        b.load_model(path / f"h{h}.json")
        b.best_iteration = manifest["best_iteration"][str(h)]
        boosters[int(h)] = b
    return QuantileForecaster(path, manifest, boosters)


def artifacts_complete(path: Path) -> list[str]:
    """Missing files for a model directory (empty list = complete)."""
    if not (path / "manifest.json").exists():
        return ["manifest.json"]
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    return [
        f"h{h}.json" for h in manifest.get("horizons", []) if not (path / f"h{h}.json").exists()
    ]

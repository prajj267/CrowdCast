"""Tuning pieces (WORKFLOW 7.3.2; doc 10 §8.3): search space, grouped CV, tuned params."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
import pytest

from crowdcast.forecasting.features import FeatureSet
from tools.training.ablation import load_tuned
from tools.training.tune import cv_score, event_mae, suggest


def test_search_space_matches_doc_10() -> None:
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=1))
    for _ in range(30):
        trial = study.ask()
        p = suggest(trial)
        study.tell(trial, 0.0)
        assert 3 <= p["max_depth"] <= 8
        assert 0.02 <= p["learning_rate"] <= 0.2
        assert 1 <= p["min_child_weight"] <= 20
        assert 0.6 <= p["subsample"] <= 1.0
        assert 0.5 <= p["colsample_bytree"] <= 1.0
        assert 0.1 <= p["reg_lambda"] <= 10.0


def test_event_mae_is_in_persons_and_averaged_per_event() -> None:
    rows = pd.DataFrame(
        {"event_id": ["a", "a", "b"], "y": [0.0, 0.0, 0.0], "capacity_abs": [100.0, 100.0, 50.0]}
    )
    # event a: errors 10 and 30 persons -> 20; event b: 5 persons -> mean of events 12.5
    assert event_mae(rows, np.array([0.1, -0.3, 0.1])) == pytest.approx(12.5)


def test_cv_score_folds_by_event() -> None:
    rng = np.random.default_rng(0)
    n = 600
    x = rng.normal(size=n)
    rows = pd.DataFrame(
        {
            "event_id": np.repeat([f"e{i}" for i in range(6)], n // 6),
            "f": x,
            "y": 0.5 * x + rng.normal(scale=0.01, size=n),
            "capacity_abs": 100.0,
        }
    )
    params = {"max_depth": 3, "learning_rate": 0.2, "min_child_weight": 1}
    score, iters = cv_score(rows, ["f"], params, folds=3, seed=1)
    assert len(iters) == 3
    assert score < 0.5 * float(np.mean(np.abs(rows["y"]))) * 100  # learns most of the signal


def test_load_tuned_refuses_other_variant(tmp_path: Path) -> None:
    f = tmp_path / "best_params.json"
    f.write_text(
        json.dumps({"run": "r", "data": "clean", "params": {"A4": {"5": {"max_depth": 4}}}}),
        encoding="utf-8",
    )
    assert load_tuned(f, FeatureSet.A4, 5, "clean") == {"max_depth": 4}
    with pytest.raises(SystemExit):
        load_tuned(f, FeatureSet.A4, 5, "noisy")

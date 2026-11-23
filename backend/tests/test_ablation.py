"""Ablation runner pieces (WORKFLOW 7.3.1): baselines from feature rows, metrics, finals guard."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crowdcast.forecasting.baselines import (
    b0_persistence,
    b1_moving_average,
    b2_linear_trend,
    b3_conservation,
)
from crowdcast.forecasting.features import FeatureSet, History, add_target, build_features
from crowdcast.forecasting.sources import published_schedule, venue_info
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config
from tools.crowdsim.params import load_regime
from tools.crowdsim.run import event_rng
from tools.crowdsim.sim import simulate
from tools.training import ablation

CONFIGS = Path(__file__).resolve().parents[2] / "configs"


@pytest.fixture(scope="module")
def run() -> tuple[History, pd.DataFrame, np.ndarray]:
    venue = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    event = load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml")
    info = venue_info(venue)
    r = simulate(venue, event, load_regime("a"), event_rng(2027, 0))
    hist = History(
        n=r.occupancy.astype(float),
        inflow=r.inflow.astype(float),
        outflow=r.outflow.astype(float),
        speed=r.mean_speed_mps.astype(float),
        offset=0,
        duration_min=420.0,
        schedule=published_schedule(event, info.codes),
    )
    rows = add_target(build_features(hist, info, FeatureSet.A4, 15), hist, info, 15)
    rows["capacity_abs"] = info.capacity[rows["zone"].to_numpy()]
    rows["event_id"] = "v1_test"
    return hist, rows, info.capacity


@pytest.mark.parametrize("k", [0, 1, 4, 9, 60, 200])
def test_baselines_from_rows_equal_the_baselines_module(
    run: tuple[History, pd.DataFrame, np.ndarray],
    k: int,
) -> None:
    hist, rows, cap = run
    preds = ablation.baseline_predictions(rows, 15)
    sel = (rows["k"] == k).to_numpy()
    n = hist.n[: k + 1]
    expected = {
        "B0": b0_persistence(n, 15),
        "B1": b1_moving_average(n, 15),
        "B2": b2_linear_trend(n, 15),
        "B3": b3_conservation(n, hist.inflow[: k + 1], hist.outflow[: k + 1], cap, 15),
    }
    order = rows.loc[sel, "zone"].to_numpy()
    for name, value in expected.items():
        np.testing.assert_allclose(
            preds[name][sel], value[order], rtol=1e-9, atol=1e-9, err_msg=name
        )


def test_per_event_metrics(run: tuple[History, pd.DataFrame, np.ndarray]) -> None:
    _, rows, _ = run
    actual = rows["n_t"].to_numpy() + rows["y"].to_numpy() * rows["capacity_abs"].to_numpy()
    perfect = ablation.per_event(rows, "oracle", 15, actual, np.column_stack([actual] * 3))
    assert perfect[0]["mae"] == 0 and perfect[0]["coverage_p10_p90"] == 1.0
    assert perfect[0]["pinball"] == 0
    off = ablation.per_event(rows, "plus10", 15, actual + 10)
    assert off[0]["mae"] == pytest.approx(10) and off[0]["bias"] == pytest.approx(10)
    assert "pinball" not in off[0]


def test_test_split_is_evaluated_only_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ablation, "FINALS", tmp_path / "finals.json")
    ablation.check_final("test_in_venue/clean", ["xgb_A4"], 2027)  # nothing registered yet
    ablation.register_final("test_in_venue/clean", ["xgb_A4"], 2027, "run1")
    with pytest.raises(SystemExit, match="evaluated ONCE"):
        ablation.check_final("test_in_venue/clean", ["xgb_A1", "xgb_A4"], 2027)
    ablation.check_final("test_in_venue/clean", ["xgb_A4"], 7)  # another seed: new configuration
    ablation.check_final("test_in_venue/noisy", ["xgb_A4"], 2027)  # other dataset: new config
    assert json.loads((tmp_path / "finals.json").read_text())[0]["run"] == "run1"


def test_feature_set_columns_are_subsets_of_a4() -> None:
    a4 = set(ablation.columns_of(FeatureSet.A4))
    for fs in FeatureSet:
        assert set(ablation.columns_of(fs)) <= a4

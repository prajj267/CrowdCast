"""FeatureBuilder tests (WORKFLOW 5.1, 5.2.1-5.2.2; doc 10 §5-7; doc 17 TC-ML-02).

Data: one CROWDSIM run of the V1 example event (SYNTHETIC).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crowdcast.forecasting.features import (
    FEATURE_WINDOW,
    GROUPS,
    FeatureSet,
    History,
    VenueInfo,
    add_target,
    build_features,
    feature_columns,
)
from crowdcast.forecasting.sources import outflow_shares, published_schedule, venue_info
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config
from tools.crowdsim.params import load_regime
from tools.crowdsim.run import event_rng
from tools.crowdsim.sim import SimResult, simulate

CONFIGS = Path(__file__).resolve().parents[2] / "configs"


@pytest.fixture(scope="module")
def sim() -> tuple[SimResult, VenueInfo, History]:
    venue_cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    event = load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml")
    r = simulate(venue_cfg, event, load_regime("a"), event_rng(2027, 0))
    flows = [(a, b, float(r.edge_flow[:, e].sum())) for e, (a, b) in enumerate(r.edges)]
    info = venue_info(venue_cfg, outflow_shares(r.zone_codes, flows))
    duration = (event.event.end_time - event.event.start_time).total_seconds() / 60
    hist = History(
        n=r.occupancy.astype(float),
        inflow=r.inflow.astype(float),
        outflow=r.outflow.astype(float),
        speed=r.mean_speed_mps.astype(float),
        offset=0,
        duration_min=duration,
        schedule=published_schedule(event, info.codes),
    )
    return r, info, hist


def _truncate(h: History, start: int, end: int) -> History:
    """Rows start..end-1 of the history (as the online cycle would receive them)."""
    return replace(
        h,
        n=h.n[start:end],
        inflow=h.inflow[start:end],
        outflow=h.outflow[start:end],
        speed=h.speed[start:end],
        offset=h.offset + start,
    )


# ------------------------------------------------------------------ TC-ML-02 (5.2.1)
@pytest.mark.parametrize("fs", list(FeatureSet))
def test_tc_ml_02_truncated_series_gives_same_features(
    sim: tuple[SimResult, VenueInfo, History], fs: FeatureSet
) -> None:
    _, info, hist = sim
    t = 200  # an issue time well inside the event
    full = build_features(_truncate(hist, 0, FEATURE_WINDOW + t + 1), info, fs, 15)
    prefix = build_features(_truncate(hist, 0, t + 1), info, fs, 15)
    cols = feature_columns(full)
    a = full[full["k"] == t][cols].to_numpy()
    b = prefix[prefix["k"] == t][cols].to_numpy()
    np.testing.assert_allclose(a, b, equal_nan=True)


@pytest.mark.parametrize("t", [59, 70, 200, 300])
def test_online_60_minute_window_equals_the_whole_event(
    sim: tuple[SimResult, VenueInfo, History], t: int
) -> None:
    """Training sees the whole event; the live cycle only its last FEATURE_WINDOW minutes.
    Row t must come out identical in both."""
    _, info, hist = sim
    whole = build_features(hist, info, FeatureSet.A4, 15)
    online = build_features(_truncate(hist, t - FEATURE_WINDOW + 1, t + 1), info, FeatureSet.A4, 15)
    online_last = online.groupby("zone").tail(1)
    cols = feature_columns(whole)
    np.testing.assert_allclose(
        online_last[cols].to_numpy(), whole[whole["k"] == t][cols].to_numpy(), equal_nan=True
    )
    assert set(online_last["minute"]) == {t + 1}  # issue time = end of bucket t


def test_changing_the_future_does_not_change_features(
    sim: tuple[SimResult, VenueInfo, History],
) -> None:
    _, info, hist = sim
    t = 150
    tampered = replace(hist, n=hist.n.copy(), inflow=hist.inflow.copy())
    tampered.n[t + 1 :] = 99_999
    tampered.inflow[t + 1 :] = 99_999
    a = build_features(hist, info, FeatureSet.A4, 30)
    b = build_features(tampered, info, FeatureSet.A4, 30)
    cols = feature_columns(a)
    np.testing.assert_allclose(
        a[a["k"] <= t][cols].to_numpy(), b[b["k"] <= t][cols].to_numpy(), equal_nan=True
    )


# ------------------------------------------------------------------ 5.2.2 schedule leakage
def test_actual_schedule_never_reaches_features(
    sim: tuple[SimResult, VenueInfo, History],
) -> None:
    """The builder's only schedule input is History.schedule, filled by published_schedule()
    from the event FILE. The realised schedule differs, so feeding it would change features."""
    r, info, hist = sim
    event = load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml")
    assert hist.schedule == published_schedule(event, info.codes)
    start = event.event.start_time
    from_file = [(it.title, it.start) for it in event.schedule]
    assert [(i.title, i.start) for i in r.published] == from_file
    realised = [(i.title, i.start) for i in r.actual if not i.is_popup]
    assert realised != from_file, "the simulator should have perturbed the schedule"
    # Proof that the choice matters: a schedule built from the realised times gives other features
    shifted = tuple(
        replace(s, start_min=(a.start - start).total_seconds() / 60,
                end_min=(a.end - start).total_seconds() / 60)
        for s, a in zip(hist.schedule, [i for i in r.actual if not i.is_popup], strict=True)
    )  # fmt: skip
    pub = build_features(hist, info, FeatureSet.A3, 15)
    real = build_features(replace(hist, schedule=shifted), info, FeatureSet.A3, 15)
    assert not np.allclose(pub["min_to_next_start"], real["min_to_next_start"])


# ------------------------------------------------------------------ 5.1.3 configs
def test_feature_sets_have_the_documented_groups(
    sim: tuple[SimResult, VenueInfo, History],
) -> None:
    _, info, hist = sim
    cols = {fs: set(feature_columns(build_features(hist, info, fs, 5))) for fs in FeatureSet}
    hist_cols = cols[FeatureSet.A1]
    assert {"u_t", "u_lag_30", "u_slope_10", "fused_u_t", "minutes_to_end"} <= hist_cols
    assert not any(c.startswith(("fin_", "active_", "nbr_")) for c in hist_cols)
    assert "b3_pred_h" in cols[FeatureSet.A2] and "active_item" not in cols[FeatureSet.A2]
    assert "active_item" in cols[FeatureSet.A3] and "b3_pred_h" not in cols[FeatureSet.A3]
    assert cols[FeatureSet.A4] == cols[FeatureSet.A4_NONBR] | {
        c for c in cols[FeatureSet.A4] if c.startswith("nbr_")
    }
    assert "nbr_flow_to_i" not in cols[FeatureSet.A4]  # not built (deviation)
    assert GROUPS[FeatureSet.A4_NONBR] == ("HIST", "FLOW", "SCHED")


def test_schedule_feature_values_for_the_headline_band(
    sim: tuple[SimResult, VenueInfo, History],
) -> None:
    _, info, hist = sim
    ms = info.codes.index("MS")
    rows = build_features(hist, info, FeatureSet.A3, 15)
    # headline band (published) 14:00-15:00 = minutes 210-270 after the 10:30 start

    def at(minute: int) -> pd.Series:
        return rows[(rows["minute"] == minute) & (rows["zone"] == ms)].iloc[0]

    before = at(200)
    assert before["min_to_next_start"] == pytest.approx(10)
    assert before["starts_within_h"] == 1 and before["active_item"] == 0
    assert before["next_item_attendance"] == pytest.approx(2500 / 3000)
    during = at(230)
    assert during["active_item"] == 1 and during["active_category_PERFORMANCE"] == 1
    assert during["min_to_next_end"] == pytest.approx(40)
    assert during["attraction"] == pytest.approx(0.95)


# ------------------------------------------------------------------ 5.1.4 target
def test_target_is_capacity_normalised_change_and_drops_the_tail(
    sim: tuple[SimResult, VenueInfo, History],
) -> None:
    _, info, hist = sim
    h = 30
    rows = add_target(build_features(hist, info, FeatureSet.A1, h), hist, info, h)
    length = hist.n.shape[0]
    assert rows["k"].max() == length - 1 - h  # t + h beyond the data: dropped
    r0 = rows.iloc[123]
    k, z = int(r0["k"]), int(r0["zone"])
    expected = (hist.n[k + h, z] - hist.n[k, z]) / info.capacity[z]
    assert r0["y"] == pytest.approx(expected)


def test_target_uses_the_truth_series_when_inputs_are_noisy(
    sim: tuple[SimResult, VenueInfo, History],
) -> None:
    # SYN-noisy (doc 12 §5.3): features and N_obs(t) from the noisy inputs, N(t+h) from truth
    _, info, hist = sim
    h = 15
    noisy = replace(hist, n=hist.n + 3.0)
    rows = add_target(build_features(noisy, info, FeatureSet.A1, h), noisy, info, h, hist.n)
    r0 = rows.iloc[200]
    k, z = int(r0["k"]), int(r0["zone"])
    expected = (hist.n[k + h, z] - (hist.n[k, z] + 3.0)) / info.capacity[z]
    assert r0["y"] == pytest.approx(expected)


def test_outflow_shares_from_training_flows() -> None:
    codes = ("A", "B", "C")
    pi = outflow_shares(codes, [("A", "B", 6), ("A", "C", 2), ("A", "OUTSIDE", 2), ("B", "A", 5)])
    np.testing.assert_allclose(pi[0], [0, 0.6, 0.2])
    np.testing.assert_allclose(pi[1], [1, 0, 0])
    np.testing.assert_allclose(pi[2], [0, 0, 0])

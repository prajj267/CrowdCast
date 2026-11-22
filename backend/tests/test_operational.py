"""Classification and operational evaluation (WORKFLOW 7.4; doc 16 §4-5)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from crowdcast.common.enums import AlertType
from crowdcast.risk.levels import Thresholds
from tools.training.ablation import prediction_frame
from tools.training.operational import (
    Alert,
    Episode,
    VenueThresholds,
    classification,
    episodes,
    event_arrays,
    operational,
    operational_summary,
    prf,
    replay,
    score_alerts,
)

T = Thresholds()  # 0.60 / 0.80 / 0.95


def test_prf_and_empty_cases() -> None:
    assert prf(8, 2, 2) == pytest.approx((0.8, 0.8, 0.8))
    p, r, f = prf(0, 0, 3)
    assert math.isnan(p) and r == 0.0 and math.isnan(f)


def test_episodes_need_two_minutes_at_high() -> None:
    u = np.array([[0.5], [0.85], [0.5], [0.81], [0.9], [0.95], [0.7], [np.nan], [0.8], [0.8]])
    eps = episodes(u, np.array([0.8]))
    # minute 1 alone is too short; 3-5 is an episode; 8-9 is one (ends with the data)
    assert eps == [Episode(0, 3, 5), Episode(0, 8, 9)]


def test_replay_uses_the_real_state_machine() -> None:
    minutes = 12
    cur = np.full((minutes, 1), 0.5)
    cur[6:9, 0] = 0.85  # CURRENT opens at k=6 (no confirmation)
    fc = np.full((minutes, 1), 0.5)
    fc[2:5, 0] = 0.9  # PREDICTED needs 2 cycles: opens at k=3
    alerts = replay(cur, {15: fc}, (T,))
    assert Alert(0, AlertType.PREDICTED, 3, 15) in alerts
    assert Alert(0, AlertType.CURRENT, 6, 0) in alerts
    # hysteresis: the PREDICTED alert resolves at k=7 (3 cycles < 0.75) and nothing reopens
    assert len(alerts) == 2


def test_score_alerts_lead_time_miss_and_false_alarm() -> None:
    eps = [Episode(0, 40, 50), Episode(1, 100, 105)]
    alerts = [
        Alert(0, AlertType.PREDICTED, 20, 15),  # covers ep 0, lead 20 min
        Alert(0, AlertType.CURRENT, 41, 0),  # also covers, later
        Alert(1, AlertType.PREDICTED, 10, 5),  # far too early: nothing within 5 + 5 -> false
    ]
    ep_rows, al_rows = score_alerts(eps, alerts)
    assert ep_rows[0]["covered"] and ep_rows[0]["lead_time"] == 20.0
    assert ep_rows[0]["source"] == "P15"
    assert not ep_rows[1]["covered"] and ep_rows[1]["source"] == "missed"
    assert [r["false_alarm"] for r in al_rows] == [False, False, True]


def test_covering_window_edges() -> None:
    ep = [Episode(0, 50, 60)]
    early_ok = score_alerts(ep, [Alert(0, AlertType.PREDICTED, 15, 30)])[0][0]
    too_early = score_alerts(ep, [Alert(0, AlertType.PREDICTED, 14, 30)])[0][0]
    late_ok = score_alerts(ep, [Alert(0, AlertType.CURRENT, 52, 0)])[0][0]
    assert early_ok["covered"] and early_ok["lead_time"] == 35.0
    assert not too_early["covered"]
    assert late_ok["covered"] and late_ok["lead_time"] == -2.0  # late = negative


def _rows(n_true: np.ndarray, h: int) -> pd.DataFrame:
    """A4-like rows of one zone-1 event with a perfect P50 (=true N(t+h))."""
    k = np.arange(len(n_true) - h)
    return pd.DataFrame(
        {"event_id": "v9_e000", "venue": "v9", "zone": 0, "k": k, "n_t": n_true[k],
         "y": (n_true[k + h] - n_true[k]) / 100.0, "capacity_abs": 100.0}
    )  # fmt: skip


def test_perfect_forecast_warns_ahead_and_classifies_perfectly() -> None:
    n = np.concatenate([np.full(40, 50.0), np.full(10, 90.0), np.full(20, 50.0)])  # 40-49 high
    frames = []
    for h in (5, 15, 30):
        rows = _rows(n, h)
        frames.append(prediction_frame(rows, h, "perfect", n[rows["k"].to_numpy() + h]))
        frames.append(prediction_frame(rows, h, "B0", rows["n_t"].to_numpy()))
    pred = pd.concat(frames, ignore_index=True)
    venues = {"v9": VenueThresholds(("A",), np.array([100.0]), (T,))}

    cls = classification(pred, venues)["summary"].set_index(["model", "horizon"])
    assert cls.loc[("perfect", 15), "f1"] == pytest.approx(1.0)
    assert cls.loc[("perfect", 15), "positives"] == 10

    ep, al, ev = operational(pred, venues, {"v9_e000": n[:, None]})
    s = operational_summary(ep, al, ev).set_index("model")
    # perfect 30-min forecast: PREDICTED opens 30 min before onset, after 2-cycle confirmation
    assert s.loc["perfect", "lead_median"] == pytest.approx(29.0)
    assert s.loc["perfect", "first_P30"] == 1.0
    assert s.loc["perfect", "missed_rate"] == 0.0
    # persistence cannot warn ahead: first warning is CURRENT at the onset (lead 0)
    assert s.loc["B0", "lead_median"] == pytest.approx(0.0)
    assert s.loc["B0", "first_CURRENT"] == 1.0


def test_event_arrays_align_on_k() -> None:
    n = np.arange(60, dtype=float)
    rows = _rows(n, 5)
    pred = prediction_frame(rows, 5, "m", n[rows["k"].to_numpy() + 5])
    cur, fc = event_arrays(pred, 1)
    assert cur[10, 0] == pytest.approx(0.10)  # N(t) / C at k = 10
    assert fc[5][10, 0] == pytest.approx(0.15)  # P50 for t + 5

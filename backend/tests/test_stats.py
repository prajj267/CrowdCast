"""Hypothesis statistics (WORKFLOW 7.3.5; experimental_design §7-8)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tools.training.ablation import per_event, post_release_mask
from tools.training.stats import (
    Comparison,
    bootstrap_ci,
    comparisons,
    holm,
    paired,
    ranking,
    report,
    run_tests,
    wilcoxon_less,
)


def test_holm_matches_hand_computation() -> None:
    # sorted p: 0.01 (x3 = 0.03), 0.02 (x2 = 0.04), 0.04 (x1 = 0.04); original order kept
    assert holm([0.04, 0.01, 0.02]) == pytest.approx([0.04, 0.03, 0.04])
    assert holm([0.5, 0.6]) == pytest.approx([1.0, 1.0])  # capped at 1
    assert holm([0.03, 0.01]) == pytest.approx([0.03, 0.02])  # step-down, monotone
    out = holm([float("nan"), 0.01])
    assert np.isnan(out[0]) and out[1] == pytest.approx(0.01)  # NaN is not counted


def test_wilcoxon_is_one_sided_in_the_right_direction() -> None:
    b = np.linspace(10, 20, 18)
    better = b - 1.0 - np.linspace(0, 0.5, 18)
    assert wilcoxon_less(better, b) < 0.001  # a clearly below b
    assert wilcoxon_less(b, better) > 0.99  # the opposite direction is not significant
    assert wilcoxon_less(b, b) == 1.0  # no differences at all


def test_bootstrap_ci_is_deterministic_and_brackets_the_statistic() -> None:
    v = np.random.default_rng(0).normal(0.1, 0.05, 30)
    med, lo, hi = bootstrap_ci(v)
    assert lo <= med <= hi
    assert med == pytest.approx(np.median(v))
    assert bootstrap_ci(v) == (med, lo, hi)  # fixed seed
    mean, lo_m, hi_m = bootstrap_ci(v, stat="mean")
    assert mean == pytest.approx(np.mean(v)) and lo_m < mean < hi_m


def _table(rng: np.random.Generator, n: int = 18) -> pd.DataFrame:
    """Synthetic per-event table: A4 < A3 < A1 < B0 with noise; A4_NONBR ~ A4."""
    base = {"B0": 30.0, "B1": 35.0, "B2": 33.0, "B3": 29.0, "xgb_A1": 20.0, "xgb_A2": 18.0,
            "xgb_A3": 17.0, "xgb_A4": 15.0, "xgb_A4_NONBR": 15.0}  # fmt: skip
    rows = []
    for h in (5, 15, 30):
        level = rng.uniform(0.8, 1.2, n)  # event difficulty shared by all models (pairing)
        for m, v in base.items():
            mae = v * h / 5 * level + rng.normal(0, 0.2, n)
            for e in range(n):
                rows.append({"event_id": f"v1_e{e:03d}", "horizon": h, "model": m,
                             "mae": mae[e], "mae_post_release": mae[e] * 1.1})  # fmt: skip
    return pd.DataFrame(rows)


def test_run_tests_finds_true_effects_and_not_null_ones() -> None:
    t = run_tests(_table(np.random.default_rng(1)))
    h1 = t[(t["hypothesis"] == "H1")]
    assert len(h1) == 3 and h1["significant"].all() and h1["practical"].all()
    nbr = t[(t["a"] == "xgb_A4") & (t["b"] == "xgb_A4_NONBR") & (t["metric"] == "mae")]
    assert not nbr["practical"].any()  # identical expected error -> no practical effect
    assert set(t["metric"]) == {"mae", "mae_post_release"}
    assert (t["p_holm"] >= t["p"]).all()
    h3 = t[t["hypothesis"] == "H3"]
    assert len(h3) == 5 * 3  # every learned model vs B0 at every horizon


def test_comparisons_skip_missing_models_and_paired_drops_nan() -> None:
    cs = comparisons({"B0", "xgb_A1", "xgb_A3"})
    assert Comparison("H1", "xgb_A3", "xgb_A1") in cs
    assert all({c.a, c.b} <= {"B0", "xgb_A1", "xgb_A3"} for c in cs)
    table = pd.DataFrame(
        {
            "event_id": ["e1", "e2", "e1", "e2"],
            "horizon": 5,
            "model": ["a", "a", "b", "b"],
            "mae_post_release": [1.0, np.nan, 2.0, 3.0],
        }
    )
    w = paired(table, Comparison("x", "a", "b", "mae_post_release"), 5)
    assert list(w.index) == ["e1"]


def test_ranking_reports_h6_order() -> None:
    r = ranking(_table(np.random.default_rng(2)))
    assert r["A4<=A3<=A1"].all()


def test_post_release_mask_uses_upstream_zones_and_target_time() -> None:
    # zone 0 -> zone 1 (zone 0 upstream of 1); zone 2 isolated. One event, three issue minutes.
    adj = np.array([[0, 1, 0], [0, 0, 0], [0, 0, 0]], dtype=float)
    since0 = [120.0, 5.0, 25.0]  # zone 0's last end: none / 5 min ago / 25 min ago
    ewh0 = [1.0, 0.0, 0.0]  # at k=0 an item in zone 0 ends within the horizon
    rows = []
    for k in range(3):
        for z in range(3):
            rows.append({"event_id": "v9_e000", "venue": "v9", "k": k, "zone": z,
                         "min_since_last_end": since0[k] if z == 0 else 120.0,
                         "ends_within_h": ewh0[k] if z == 0 else 0.0})  # fmt: skip
    df = pd.DataFrame(rows).sample(frac=1.0, random_state=0)  # order must not matter
    mask = pd.Series(post_release_mask(df, 15, {"v9": adj}), index=df.index).sort_index()
    got = mask.to_numpy().reshape(3, 3)
    # h = 15: window is e in (t - 15, t + 15]; k=0 ends ahead (yes), k=1 5 min ago (yes),
    # k=2 25 min ago (no). Only zone 1 (downstream of 0) is flagged; zone 0 itself is not.
    np.testing.assert_array_equal(got[:, 1], [True, True, False])
    assert not got[:, 0].any() and not got[:, 2].any()


def test_per_event_strata() -> None:
    rows = pd.DataFrame(
        {
            "event_id": ["e1"] * 4,
            "n_t": [10.0, 10.0, 80.0, 80.0],
            "y": [0.0, 0.0, 0.0, 0.0],
            "capacity_abs": [100.0] * 4,
        }
    )
    p50 = np.array([12.0, 10.0, 70.0, 80.0])  # errors 2, 0, 10, 0
    rec = per_event(rows, "m", 5, p50, post_release=np.array([True, False, False, False]))[0]
    assert rec["mae"] == pytest.approx(3.0)
    assert rec["mae_peak"] == pytest.approx(5.0) and rec["rows_peak"] == 2  # u = 0.8 rows
    assert rec["mae_post_release"] == pytest.approx(2.0) and rec["rows_post_release"] == 1
    none = per_event(rows, "m", 5, p50, post_release=np.zeros(4, dtype=bool))[0]
    assert np.isnan(none["mae_post_release"]) and none["rows_post_release"] == 0


def test_report_writes_files(tmp_path: Path) -> None:
    _table(np.random.default_rng(3)).to_csv(tmp_path / "per_event.csv", index=False)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"run": "r", "split": "validation", "data_origin": "SYNTHETIC"}),
        encoding="utf-8",
    )
    text = report(tmp_path, "abc")
    assert "not hypothesis tests" in text
    assert (tmp_path / "statistics.csv").exists() and (tmp_path / "statistics.md").exists()

"""Doc 16 results tables from pipeline output (WORKFLOW 7.5.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tools import report

MODELS = ["B0", "B1", "B2", "B3", "xgb_A1", "xgb_A2", "xgb_A3", "xgb_A4", "xgb_A4_NONBR"]


def make_run(root: Path, name: str, split: str, data: str, seed: int, a4_mae: float) -> None:
    """A minimal ablation run folder: 2 events, every model and horizon."""
    d = root / name
    d.mkdir()
    manifest = {
        "run": name,
        "split": split,
        "final": True,
        "seed": seed,
        "git_commit": "abcdef0123",
        "data_origin": "SYNTHETIC",
        "data": f"SYN-{data} inputs, CROWDSIM regime A",
        "params": f"tuned: configs/tuning/syn_{data}.json",
        "train_events": 84,
        "target_events": 2,
    }
    (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    pe = [
        {
            "event_id": ev,
            "horizon": h,
            "model": m,
            "rows": 100,
            "mae": a4_mae + ev if m == "xgb_A4" else 50.0 + ev,
            "coverage_conformal": 0.80 if m.startswith("xgb") else None,
            "width_conformal": 10.0 if m.startswith("xgb") else None,
            "coverage_p10_p90": 0.75 if m.startswith("xgb") else None,
        }
        for ev in (0, 2)
        for h in report.HORIZONS
        for m in MODELS
    ]
    pd.DataFrame(pe).to_csv(d / "per_event.csv", index=False)
    st = [
        {
            "hypothesis": hyp,
            "a": a,
            "b": b,
            "metric": metric,
            "horizon": h,
            "median_rel_reduction": 0.10 if seed == 2027 else 0.03,
            "ci_low": 0.05,
            "ci_high": 0.15,
            "p_holm": 0.01,
            "significant": True,
            "practical": seed == 2027,
        }
        for _, hyp, a, b, metric in report.HYPOTHESES
        for h in report.HORIZONS
    ]
    pd.DataFrame(st).to_csv(d / "statistics.csv", index=False)
    cl = [
        {
            "horizon": h,
            "model": m,
            "positives": 40,
            "precision": 0.9,
            "recall": 0.8,
            "f1": 0.847,
            "f1_ci_low": 0.8,
            "f1_ci_high": 0.9,
        }
        for h in report.HORIZONS
        for m in report.OP_MODELS
    ]
    pd.DataFrame(cl).to_csv(d / "classification.csv", index=False)
    op = [
        {
            "model": m,
            "episodes": 10,
            "missed_rate": 0.1 if seed == 2027 else 0.3,
            "lead_median": 4.0,
            "lead_q25": 1.0,
            "lead_q75": 9.0,
            "alerts": 12,
            "false_alarm_rate": 0.25,
            "false_alarms_per_hour": 0.5,
            "first_P30": 0.4,
            "first_P15": 0.2,
            "first_P5": 0.1,
            "first_CURRENT": 0.2,
        }
        for m in report.OP_MODELS
    ]
    pd.DataFrame(op).to_csv(d / "operational.csv", index=False)


@pytest.fixture
def finals_path(tmp_path: Path) -> Path:
    make_run(tmp_path, "r2027", "test_in_venue", "clean", 2027, a4_mae=10.0)
    make_run(tmp_path, "r2028", "test_in_venue", "clean", 2028, a4_mae=12.0)
    entries = [
        {"dataset": "test_in_venue/clean", "model": "xgb_A4", "seed": s, "run": f"r{s}"}
        for s in (2027, 2028)
    ]
    path = tmp_path / "finals.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_render_puts_pipeline_numbers_in_the_tables(finals_path: Path) -> None:
    finals = report.load_finals(finals_path)
    text = report.render(finals, [], [], "abcdef0")
    label = report.DATASET_LABEL["test_in_venue/clean"]
    acc = next(
        ln
        for ln in report.accuracy_section(finals).splitlines()
        if ln.startswith(f"| {label} | 5 ")
    )
    # A4 mean over events 10 and 12 = 11 (seed 2027); seeds 11 and 13 -> range; skill 1 - 11/51
    assert f"| 11.00 [10.00, 12.00] | 11.00{report.DASH}13.00 |" in acc
    assert acc.endswith("| 0.784 |")
    assert "sig 2/2, sig+practical 1/2" in text  # practical only in seed 2027
    assert "2 of 2 seeds" in text  # H6: A4 (11) <= A3 (51) <= A1 (51)
    assert f"10.0 %{report.DASH}30.0 %" in text  # missed rate over seeds
    assert "REAL (staged / event)" in text and "not measured" in text


def test_load_finals_rejects_a_manifest_that_does_not_match(finals_path: Path) -> None:
    m = finals_path.parent / "r2028" / "manifest.json"
    m.write_text(m.read_text().replace('"final": true', '"final": false'), encoding="utf-8")
    with pytest.raises(SystemExit, match="does not match"):
        report.load_finals(finals_path)


def test_load_finals_rejects_wrong_data_origin(finals_path: Path) -> None:
    m = finals_path.parent / "r2027" / "manifest.json"
    m.write_text(m.read_text().replace("SYN-clean", "SYN-noisy"), encoding="utf-8")
    with pytest.raises(SystemExit, match="expected SYNTHETIC SYN-clean"):
        report.load_finals(finals_path)


def test_replace_block_only_touches_the_generated_part() -> None:
    doc = f"head\n{report.BEGIN}\nold\n{report.END}\ntail\n"
    out = report.replace_block(doc, "new\n")
    assert out == f"head\n{report.BEGIN}\n\nnew\n\n{report.END}\ntail\n"
    assert report.replace_block(out, "new\n") == out  # idempotent
    with pytest.raises(SystemExit, match="marker"):
        report.replace_block("no markers", "x")


def test_cv_sections_read_summaries(tmp_path: Path) -> None:
    run = tmp_path / "20260101T000000Z"
    run.mkdir()
    band = {"n": 4, "mae": 2.5, "rmse": 3.0, "bias": -2.5, "relative_mae": 0.25, "mean_true": 10.0}
    summary = {"run": run.name, "results": {"mall": {"yolox_s_tiled": {"all": band}}}}
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    counts = report.cv_count_section([run / "summary.json"])
    assert "| mall | yolox_s_tiled | all | 4 | 10.0 | 2.50 | 3.00 | -2.50 | 0.250 |" in counts
    flows = tmp_path / "flows_x.json"
    seq = {
        "sequence": "S",
        "length_s": 10.0,
        "true_crossings": {"up": 3, "down": 1},
        "est_crossings": {"up": 2, "down": 0},
        "precision": None,
        "recall_p_det": 0.5,
        "net_flow": {"true": -2, "estimated": -2, "bias": 0},
    }
    flows.write_text(json.dumps({"results": [seq]}), encoding="utf-8")
    assert "| S | 10.0 | 4 | 2 | n/a | 0.500 | -2 / -2 | 0 |" in report.cv_flow_section([flows])

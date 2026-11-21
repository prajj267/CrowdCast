"""Ablation runner: feature sets x horizons, XGBoost vs baselines B0-B3 (WORKFLOW 7.3.1;
RESEARCH/experimental_design.md §4-7; CLAUDE.md §5).

- Features are built ONCE per horizon as the A4 superset (every other set is a column subset)
  and cached under data/datasets/; each feature set then selects its own columns.
- Baselines come from the same rows: B0 = N(t), B1 = 5-min rolling mean, B2 = N(t) + h * 10-min
  OLS slope, B3 = conservation forecast - exactly doc 10 §2 (checked against the baselines
  module in tests).
- Development runs score the VALIDATION split. A test split needs ``--final`` and is evaluated
  ONCE per (dataset, feature set, seed): finals are registered and repeats are refused.

Output: runs/ablation/<run>/per_event.csv (one row per event x horizon x model - the unit of
the paired Wilcoxon tests, 7.3.5) + manifest.json.

Usage (from backend/, clean tree):
  uv run python -u -m tools.training.ablation --split validation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.forecasting.conformal import apply_offset, conformal_offset, conformity_scores
from crowdcast.forecasting.features import FeatureSet, History, build_features, feature_columns
from crowdcast.forecasting.interfaces import HORIZONS
from crowdcast.forecasting.sources import venue_info
from crowdcast.forecasting.xgb import QUANTILES, predict_change, to_occupancy, train_booster
from crowdcast.venue_graph.interfaces import load_venue_config
from tools.training.dataset import build_split, data_hash, venue_infos
from tools.training.splits import load_splits
from tools.training.train import git_commit

DATASETS = REPO_ROOT / "data" / "datasets"
RUNS = REPO_ROOT / "runs" / "ablation"
FINALS = RUNS / "finals.json"
TEST_SPLITS = ("test_in_venue", "test_new_venue")
B3_CAP = 1.5


# ---------------------------------------------------------------------- feature cache
def columns_of(fs: FeatureSet) -> list[str]:
    """Feature columns of a set (built on a tiny dummy history; only the names matter)."""
    cfg = load_venue_config(REPO_ROOT / "configs" / "venues" / "v1.yaml")
    info = venue_info(cfg)
    z = len(info.codes)
    hist = History(
        n=np.ones((3, z)),
        inflow=np.zeros((3, z)),
        outflow=np.zeros((3, z)),
        speed=np.zeros((3, z)),
        offset=0,
        duration_min=60.0,
    )
    return feature_columns(build_features(hist, info, fs, 5))


def cached_split(
    split: str, ids: list[str], horizon: int, train_ids: list[str], variant: str = "clean"
) -> pd.DataFrame:
    """A4 feature rows (+ target) for one split, horizon and data variant, cached by hash."""
    key = hashlib.sha256((data_hash(ids, variant) + data_hash(train_ids)).encode()).hexdigest()[:16]
    path = DATASETS / "regime_a" / variant / "A4" / f"h{horizon}_{split}_{key}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    venues = sorted({e.split("_")[0] for e in ids})
    rows = build_split(ids, venue_infos(train_ids, venues), FeatureSet.A4, horizon, variant)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(path, index=False)
    return rows


# ---------------------------------------------------------------------- baselines from rows
def baseline_predictions(rows: pd.DataFrame, horizon: int) -> dict[str, np.ndarray]:
    """B0-B3 point forecasts (persons) from A4 rows, identical to doc 10 §2 definitions."""
    cap = rows["capacity_abs"].to_numpy()
    n = rows["n_t"].to_numpy()
    b1 = rows["u_roll_mean_5"].to_numpy() * cap
    slope = np.nan_to_num(rows["u_slope_10"].to_numpy()) * cap  # one point -> slope 0
    b3 = np.clip(n + rows["b3_pred_h"].to_numpy() * cap, 0, B3_CAP * cap)
    return {"B0": n, "B1": b1, "B2": n + horizon * slope, "B3": b3}


# ---------------------------------------------------------------------- conformal (7.3.3)
def actual_of(rows: pd.DataFrame) -> np.ndarray:
    return np.asarray(
        rows["n_t"].to_numpy() + rows["y"].to_numpy() * rows["capacity_abs"].to_numpy()
    )


def offset_on(rows: pd.DataFrame, q: np.ndarray) -> float:
    return conformal_offset(conformity_scores(q, actual_of(rows), rows["capacity_abs"]))


def conformalised(
    target: pd.DataFrame,
    q_target: np.ndarray,
    calib: pd.DataFrame | None = None,
    q_calib: np.ndarray | None = None,
) -> np.ndarray:
    """Split-conformal P10-P90 for the target rows (doc 10 §11).

    With calibration rows (a test split: calib = validation) one offset from all of them.
    Without (the validation split itself): 2-fold cross-calibration BY EVENT - each half of
    the events is adjusted with the offset calibrated on the other half, so the reported
    coverage is measured on events not used for calibration.
    """
    cap = target["capacity_abs"].to_numpy()
    if calib is not None and q_calib is not None:
        return apply_offset(q_target, offset_on(calib, q_calib), cap)
    events = sorted(target["event_id"].unique())
    half = target["event_id"].isin(events[::2]).to_numpy()
    out = q_target.copy()
    for part in (half, ~half):
        off = offset_on(target[~part], q_target[~part])
        out[part] = apply_offset(q_target[part], off, cap[part])
    return out


# ---------------------------------------------------------------------- metrics
def per_event(
    rows: pd.DataFrame,
    model: str,
    horizon: int,
    p50: np.ndarray,
    quantiles: np.ndarray | None = None,
    conformal: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    """MAE / RMSE (persons); for quantile models pinball loss, P10-P90 coverage and width, raw
    and after split-conformal calibration."""
    actual = rows["n_t"].to_numpy() + rows["y"].to_numpy() * rows["capacity_abs"].to_numpy()
    out = []
    for eid, idx in rows.groupby("event_id").indices.items():
        err = p50[idx] - actual[idx]
        rec: dict[str, Any] = {
            "event_id": eid,
            "venue": str(eid).split("_")[0],
            "horizon": horizon,
            "model": model,
            "rows": len(idx),
            "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err**2))),
            "bias": float(np.mean(err)),
        }
        if quantiles is not None:
            q = quantiles[idx]
            a = actual[idx]
            rec["pinball"] = float(
                np.mean(
                    [
                        np.mean(np.maximum(al * (a - q[:, k]), (al - 1) * (a - q[:, k])))
                        for k, al in enumerate(QUANTILES)
                    ]
                )
            )
            rec["coverage_p10_p90"] = float(np.mean((a >= q[:, 0]) & (a <= q[:, 2])))
            rec["width_p10_p90"] = float(np.mean(q[:, 2] - q[:, 0]))
        if conformal is not None:
            c = conformal[idx]
            a = actual[idx]
            rec["coverage_conformal"] = float(np.mean((a >= c[:, 0]) & (a <= c[:, 2])))
            rec["width_conformal"] = float(np.mean(c[:, 2] - c[:, 0]))
        out.append(rec)
    return out


# ---------------------------------------------------------------------- tuned parameters
def load_tuned(path: Path, fs: FeatureSet, horizon: int, variant: str) -> dict[str, Any]:
    """Tuned parameters of one cell (tools/training/tune.py output); refuses a file tuned on
    the other data variant."""
    d = json.loads(path.read_text(encoding="utf-8"))
    if d["data"] != variant:
        raise SystemExit(f"{path} was tuned on SYN-{d['data']}, not SYN-{variant}")
    params: dict[str, Any] = d["params"][fs.value][str(horizon)]
    return params


# ---------------------------------------------------------------------- finals guard
def check_final(dataset: str, models: list[str], seed: int) -> None:
    done = json.loads(FINALS.read_text(encoding="utf-8")) if FINALS.exists() else []
    seen = {(d["dataset"], d["model"], d["seed"]) for d in done}
    repeated = [m for m in models if (dataset, m, seed) in seen]
    if repeated:
        raise SystemExit(
            f"{dataset} was already evaluated for {repeated} (seed {seed}); a test split is "
            "evaluated ONCE per final configuration (CLAUDE.md §5)"
        )


def register_final(dataset: str, models: list[str], seed: int, run: str) -> None:
    done = json.loads(FINALS.read_text(encoding="utf-8")) if FINALS.exists() else []
    done += [{"dataset": dataset, "model": m, "seed": seed, "run": run} for m in models]
    FINALS.parent.mkdir(parents=True, exist_ok=True)
    FINALS.write_text(json.dumps(done, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------- runner
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="validation", choices=["validation", *TEST_SPLITS])
    parser.add_argument("--final", action="store_true", help="required for a test split")
    parser.add_argument("--feature-sets", nargs="*", type=FeatureSet, default=list(FeatureSet))
    parser.add_argument("--horizons", nargs="*", type=int, default=list(HORIZONS))
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument(
        "--data",
        choices=["clean", "noisy"],
        default="clean",
        help="SYN-clean or SYN-noisy inputs (targets always clean)",
    )
    parser.add_argument(
        "--params", type=Path, help="best_params.json of a tuning run (default: untuned)"
    )
    args = parser.parse_args(argv)
    if args.params is not None and not args.params.is_absolute():
        args.params = (Path.cwd() / args.params).resolve()
    commit = git_commit()
    if commit.endswith("(dirty working tree)"):
        print("uncommitted changes: commit first (results must come from committed code)")
        return 2
    if args.split in TEST_SPLITS and not args.final:
        print(f"{args.split} is a TEST split: pass --final (evaluated once per configuration)")
        return 2
    models = [f"xgb_{fs.value}" for fs in args.feature_sets]
    if args.split in TEST_SPLITS:
        check_final(args.split, models, args.seed)

    splits = load_splits()
    train_ids, val_ids, target_ids = splits["train"], splits["validation"], splits[args.split]
    run = utc_now().strftime("%Y%m%dT%H%M%SZ")
    out = RUNS / run
    out.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for h in args.horizons:
        train = cached_split("train", train_ids, h, train_ids, args.data)
        val = cached_split("validation", val_ids, h, train_ids, args.data)
        target = (
            val
            if args.split == "validation"
            else cached_split(args.split, target_ids, h, train_ids, args.data)
        )
        for name, pred in baseline_predictions(target, h).items():
            records += per_event(target, name, h, pred)
        for fs in args.feature_sets:
            cols = columns_of(fs)
            params = None if args.params is None else load_tuned(args.params, fs, h, args.data)
            booster = train_booster(
                train[cols], train["y"], val[cols], val["y"], seed=args.seed, params=params
            )
            q = to_occupancy(
                target["n_t"], target["capacity_abs"], predict_change(booster, target[cols])
            )
            if args.split == "validation":
                conf = conformalised(target, q)
            else:
                q_val = to_occupancy(
                    val["n_t"], val["capacity_abs"], predict_change(booster, val[cols])
                )
                conf = conformalised(target, q, val, q_val)
            records += per_event(target, f"xgb_{fs.value}", h, q[:, 1], q, conf)
            print(
                f"h={h:2d} {fs.value:9s} best_it {booster.best_iteration:4d} "
                f"({time.perf_counter() - t0:.0f} s)"
            )
    table = pd.DataFrame(records)
    table.to_csv(out / "per_event.csv", index=False)
    summary = table.groupby(["horizon", "model"])["mae"].mean().unstack("model").round(2)
    print(f"mean MAE over {args.split} events (persons):\n{summary}")
    xgb_rows = table[table["model"].str.startswith("xgb_")]
    cov = xgb_rows.groupby(["horizon", "model"])[["coverage_p10_p90", "coverage_conformal"]]
    print(f"P10-P90 coverage raw / conformal (nominal 0.80):\n{cov.mean().round(3)}")
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "run": run,
                "split": args.split,
                "final": args.final,
                "seed": args.seed,
                "git_commit": commit,
                "data_origin": "SYNTHETIC",
                "data": f"SYN-{args.data} inputs (targets: true simulator states), "
                "CROWDSIM regime A"
                + (
                    "; noise: configs/crowdsim/noise_calibrated.yaml"
                    if args.data == "noisy"
                    else ""
                ),
                "feature_sets": [fs.value for fs in args.feature_sets],
                "horizons": args.horizons,
                "params": "untuned defaults (forecasting/xgb.py DEFAULT_PARAMS)"
                if args.params is None
                else f"tuned: {args.params.relative_to(REPO_ROOT).as_posix()}",
                "train_events": len(train_ids),
                "target_events": len(target_ids),
                "data_hash_train_val": data_hash(train_ids + val_ids, args.data),
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    if args.split in TEST_SPLITS:
        register_final(args.split, models, args.seed, run)
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

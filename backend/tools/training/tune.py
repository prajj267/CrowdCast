"""Hyper-parameter tuning: Optuna TPE with GroupKFold by event (WORKFLOW 7.3.2; doc 10 §8.3;
RESEARCH/experimental_design.md §5 step 3).

- Only TRAINING events are used (CLAUDE.md §5): folds are GroupKFold by event inside the
  training split; validation and test events are never seen here.
- The MEDIAN model is tuned (XGBoost quantile loss, alpha 0.5); the 0.1/0.9 models reuse its
  parameters (doc 10 §8.3). Inside each fold, early stopping uses the held-out fold.
- Objective: mean over folds of the per-event MAE in persons (the primary metric, doc 16).
- Search space exactly doc 10 §8.3. Budget: 20 trials x 3 folds instead of 50 x 5 (WORKFLOW
  Deviation log, CPU time; chosen by the developer).

Output: runs/tuning/<run>/best_params.json (feature set -> horizon -> params; written after
every cell, so a stopped run keeps the finished cells), trials.csv, manifest.json.

Usage (from backend/, clean tree):
  uv run python -u -m tools.training.tune --data clean
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import GroupKFold

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.forecasting.features import FeatureSet
from crowdcast.forecasting.interfaces import HORIZONS
from crowdcast.forecasting.xgb import train_booster
from tools.training.ablation import cached_split, columns_of
from tools.training.dataset import data_hash
from tools.training.splits import load_splits
from tools.training.train import git_commit

RUNS = REPO_ROOT / "runs" / "tuning"
MEDIAN = {"quantile_alpha": 0.5}


def suggest(trial: optuna.Trial) -> dict[str, Any]:
    """XGBoost search space of doc 10 §8.3 (n_estimators: cap 2000 + early stopping)."""
    return {
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 10.0, log=True),
    }


def event_mae(rows: pd.DataFrame, change: np.ndarray) -> float:
    """Mean over events of the MAE in persons of a predicted normalised change."""
    err = np.abs(change - rows["y"].to_numpy()) * rows["capacity_abs"].to_numpy()
    return float(pd.Series(err).groupby(rows["event_id"].to_numpy()).mean().mean())


def cv_score(
    rows: pd.DataFrame, cols: list[str], params: dict[str, Any], folds: int, seed: int
) -> tuple[float, list[int]]:
    """GroupKFold-by-event score of the median model; also the best iteration per fold."""
    scores, iters = [], []
    for fit_idx, held_idx in GroupKFold(n_splits=folds).split(rows, groups=rows["event_id"]):
        fit, held = rows.iloc[fit_idx], rows.iloc[held_idx]
        booster = train_booster(
            fit[cols], fit["y"], held[cols], held["y"], seed=seed, params={**params, **MEDIAN}
        )
        best = booster.best_iteration
        change = booster.predict(xgb.DMatrix(held[cols]), iteration_range=(0, best + 1))
        scores.append(event_mae(held, np.asarray(change, dtype=np.float64)))
        iters.append(best)
    return float(np.mean(scores)), iters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", choices=["clean", "noisy"], default="clean")
    parser.add_argument("--feature-sets", nargs="*", type=FeatureSet, default=list(FeatureSet))
    parser.add_argument("--horizons", nargs="*", type=int, default=list(HORIZONS))
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2027)
    args = parser.parse_args(argv)
    commit = git_commit()
    if commit.endswith("(dirty working tree)"):
        print("uncommitted changes: commit first (results must come from committed code)")
        return 2

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    train_ids = load_splits()["train"]
    run = utc_now().strftime("%Y%m%dT%H%M%SZ")
    out = RUNS / run
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run": run,
        "git_commit": commit,
        "data_origin": "SYNTHETIC",
        "data": f"SYN-{args.data} inputs (targets: true simulator states), CROWDSIM regime A",
        "events": f"training split only ({len(train_ids)} events)",
        "data_hash_train": data_hash(train_ids, args.data),
        "method": f"Optuna TPE (seed {args.seed}), {args.trials} trials, GroupKFold "
        f"{args.folds} folds by event; median model (alpha 0.5); objective mean per-event MAE "
        "(persons); early stopping on the held-out fold",
        "feature_sets": [fs.value for fs in args.feature_sets],
        "horizons": args.horizons,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    best: dict[str, dict[str, Any]] = {}
    trials: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    for h in args.horizons:
        rows = cached_split("train", train_ids, h, train_ids, args.data)
        for fs in args.feature_sets:
            cols = columns_of(fs)

            def objective(
                trial: optuna.Trial, cols: list[str] = cols, rows: pd.DataFrame = rows
            ) -> float:
                params = suggest(trial)
                score, iters = cv_score(rows, cols, params, args.folds, args.seed)
                trial.set_user_attr("best_iterations", iters)
                return score

            study = optuna.create_study(
                direction="minimize", sampler=optuna.samplers.TPESampler(seed=args.seed)
            )
            study.optimize(objective, n_trials=args.trials)
            for t in study.trials:
                trials.append(
                    {
                        "feature_set": fs.value,
                        "horizon": h,
                        "trial": t.number,
                        "cv_mae": t.value,
                        **t.params,
                        "best_iterations": t.user_attrs.get("best_iterations"),
                    }
                )
            best.setdefault(fs.value, {})[str(h)] = study.best_params
            print(
                f"h={h:2d} {fs.value:9s} best CV MAE {study.best_value:7.2f} "
                f"{study.best_params} ({time.perf_counter() - t0:.0f} s)",
                flush=True,
            )
            (out / "best_params.json").write_text(
                json.dumps({"run": run, "data": args.data, "params": best}, indent=1),
                encoding="utf-8",
            )
            pd.DataFrame(trials).to_csv(out / "trials.csv", index=False)
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

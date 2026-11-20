"""Train an XGBoost quantile model and register it (WORKFLOW 5.3.2; CLAUDE.md §5).

  build datasets (train + validation splits from configs/splits.json)
  -> one quantile booster per horizon, early stopping on validation
  -> validation metrics, compared with B0 persistence (TEST SPLITS ARE NOT TOUCHED)
  -> model directory with a manifest (config, data hash, seed, git commit, metrics)
  -> row in model_versions (inactive until activated)

Usage (from backend/, Postgres running):
  uv run python -m tools.training.train --feature-set A4
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.time import utc_now
from crowdcast.forecasting.features import FeatureSet, feature_columns
from crowdcast.forecasting.interfaces import HORIZONS
from crowdcast.forecasting.xgb import (
    DEFAULT_PARAMS,
    QUANTILES,
    predict_change,
    save_model,
    to_occupancy,
    train_booster,
)
from crowdcast.storage.interfaces import ModelVersion, session_scope
from tools.training.dataset import build_split, data_hash, shares_for_manifest, venue_infos
from tools.training.splits import SPLITS_FILE, load_splits

SEED = 2027
MODEL_ROOT = REPO_ROOT / "models" / "xgb"


def git_commit() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return sha + (" (dirty working tree)" if dirty else "")


def pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


def validation_metrics(val: pd.DataFrame, quant: np.ndarray, horizon: int) -> dict[str, float]:
    """On the VALIDATION split only, in persons: model vs B0 persistence."""
    n_now = val["n_t"].to_numpy()
    actual = n_now + val["y"].to_numpy() * val["capacity_abs"].to_numpy()
    return {
        "rows": float(len(val)),
        "mae_p50": float(np.mean(np.abs(quant[:, 1] - actual))),
        "mae_b0": float(np.mean(np.abs(n_now - actual))),
        "pinball_mean": float(
            np.mean([pinball(actual, quant[:, k], a) for k, a in enumerate(QUANTILES)])
        ),
        "coverage_p10_p90": float(np.mean((actual >= quant[:, 0]) & (actual <= quant[:, 2]))),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-set", type=FeatureSet, default=FeatureSet.A4)
    parser.add_argument("--horizons", type=int, nargs="*", default=list(HORIZONS))
    parser.add_argument("--no-register", action="store_true", help="skip the model_versions row")
    args = parser.parse_args(argv)
    fs: FeatureSet = args.feature_set

    splits = load_splits()
    train_ids, val_ids = splits["train"], splits["validation"]
    venues = sorted({e.split("_")[0] for e in train_ids})
    infos = venue_infos(train_ids, venues)
    version = utc_now().strftime("%Y%m%dT%H%M%SZ")
    name = f"xgb_{fs.value}"
    path = MODEL_ROOT / name / version
    t0 = time.perf_counter()

    boosters, best, metrics, columns = {}, {}, {}, []
    for h in args.horizons:
        train = build_split(train_ids, infos, fs, h)
        val = build_split(val_ids, infos, fs, h)
        columns = feature_columns(train.drop(columns=["event_id", "venue", "capacity_abs"]))
        booster = train_booster(train[columns], train["y"], val[columns], val["y"], seed=SEED)
        quant = to_occupancy(val["n_t"], val["capacity_abs"], predict_change(booster, val[columns]))
        boosters[h] = booster
        best[str(h)] = int(booster.best_iteration)
        metrics[str(h)] = validation_metrics(val, quant, h)
        print(
            f"h={h:2d}: {len(train)} train rows, best iteration {booster.best_iteration}, "
            f"VALIDATION MAE p50 {metrics[str(h)]['mae_p50']:.2f} vs B0 "
            f"{metrics[str(h)]['mae_b0']:.2f} persons, P10-P90 coverage "
            f"{metrics[str(h)]['coverage_p10_p90']:.3f} ({time.perf_counter() - t0:.0f} s)"
        )

    manifest: dict[str, Any] = {
        "name": name,
        "version": version,
        "model_family": "XGBOOST",
        "feature_set": fs.value,
        "horizons": args.horizons,
        "quantiles": list(QUANTILES),
        "feature_columns": columns,
        "params": {**DEFAULT_PARAMS, "num_boost_round": 2000, "early_stopping_rounds": 50},
        "params_note": "untuned defaults (placeholders) - Optuna tuning in Phase 7",
        "best_iteration": best,
        "seed": SEED,
        "data_origin": "SYNTHETIC",
        "data": "SYN-clean (true simulator states as inputs), CROWDSIM regime A",
        "splits_file": SPLITS_FILE.name,
        "train_events": len(train_ids),
        "validation_events": len(val_ids),
        "data_hash": data_hash(train_ids + val_ids),
        "git_commit": git_commit(),
        "outflow_shares": shares_for_manifest(infos),
        "validation_metrics": metrics,
        "note": "metrics are on the VALIDATION split only; test splits untouched",
    }
    save_model(path, boosters, manifest)
    print(f"written {path}")
    if not args.no_register:
        with session_scope() as s:
            row = ModelVersion(
                name=name, version=version, model_family="XGBOOST", feature_set=fs.value,
                artifact_path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                trained_on={"data_hash": manifest["data_hash"], "splits": SPLITS_FILE.name,
                            "train_events": len(train_ids), "data_origin": "SYNTHETIC"},
                metrics={"validation": metrics}, is_active=False,
            )  # fmt: skip
            s.add(row)
            s.flush()
            print(
                f"registered model_version_id={row.model_version_id} ({name} {version}, inactive)"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())

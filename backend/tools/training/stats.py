"""Hypothesis statistics on an ablation run (WORKFLOW 7.3.5; RESEARCH/experimental_design.md
§7-8; research_hypotheses.md H1-H4, H6, H7; doc 16).

Unit of analysis: the EVENT (per-event MAE from per_event.csv), because minutes within an event
are dependent. For each comparison "model a beats model b" and each horizon:

- one-sided Wilcoxon signed-rank test on the paired per-event MAE (H1: a < b);
- Holm correction across the three horizons within each comparison (family = one comparison);
- effect size: median over events of the relative MAE reduction (b - a) / b, with a 95 %
  percentile bootstrap CI (10,000 resamples of events, seed 2027);
- practical threshold: a median reduction >= 5 % (declared in advance).

H6 (ranking A4 <= A3 <= A1 under noise) is read from the mean-MAE ranking of a SYN-noisy run;
H7 (80 % intervals cover 75-85 %) from per-event conformal coverage with a bootstrap CI.

A VALIDATION run gives development numbers only; hypothesis tests are the TEST-split runs
(evaluated once). Output: statistics.csv / statistics.md in the run folder.

Usage (from backend/, clean tree):
  uv run python -m tools.training.stats ../runs/ablation/<run>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from tools.training.train import git_commit

ALPHA = 0.05
N_BOOT = 10_000
SEED = 2027
PRACTICAL = 0.05  # >= 5 % median relative MAE reduction (experimental_design §7)
COVERAGE_BAND = (0.75, 0.85)  # H7
BASELINES = ("B0", "B1", "B2", "B3")


@dataclass(frozen=True)
class Comparison:
    hypothesis: str
    a: str  # the model expected to be better (lower error)
    b: str
    metric: str = "mae"


def comparisons(models: set[str]) -> list[Comparison]:
    """The pre-registered comparisons (research_hypotheses.md) for the models present."""
    xgb = sorted(m for m in models if m.startswith("xgb_"))
    out = [
        Comparison("H1", "xgb_A3", "xgb_A1"),
        Comparison("H2", "xgb_A2", "xgb_A1"),
        *[Comparison("H3", m, "B0") for m in xgb],
        Comparison("H4", "xgb_A4", "xgb_A4_NONBR"),
        Comparison("H4", "xgb_A4", "xgb_A4_NONBR", "mae_post_release"),
        Comparison("H4", "xgb_A4", "xgb_A2"),
        Comparison("H4", "xgb_A4", "xgb_A3"),
        # every learned model against every other baseline (CLAUDE.md §5)
        *[Comparison("baselines", m, b) for m in xgb for b in BASELINES[1:]],
    ]
    return [c for c in out if c.a in models and c.b in models]


# ---------------------------------------------------------------------- primitives
def wilcoxon_less(a: np.ndarray, b: np.ndarray) -> float:
    """One-sided p-value for 'a is smaller than b' (paired); 1.0 if all differences are 0."""
    d = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    if not np.any(d != 0):
        return 1.0
    return float(sps.wilcoxon(d, alternative="less").pvalue)


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (monotone, capped at 1); NaN stays NaN."""
    p = np.asarray(pvalues, dtype=np.float64)
    ok = np.flatnonzero(~np.isnan(p))
    adj = np.full(len(p), np.nan)
    m = len(ok)
    running = 0.0
    for rank, i in enumerate(ok[np.argsort(p[ok], kind="stable")]):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return [float(x) for x in adj]


def bootstrap_ci(
    values: np.ndarray, stat: str = "median", n_boot: int = N_BOOT, seed: int = SEED
) -> tuple[float, float, float]:
    """(statistic, 2.5 %, 97.5 %) by percentile bootstrap over the given per-event values."""
    v = np.asarray(values, dtype=np.float64)
    fn = np.median if stat == "median" else np.mean
    if len(v) == 0:
        return math.nan, math.nan, math.nan
    rng = np.random.default_rng(seed)
    boots = fn(v[rng.integers(0, len(v), size=(n_boot, len(v)))], axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(fn(v)), float(lo), float(hi)


# ---------------------------------------------------------------------- tests
def paired(table: pd.DataFrame, c: Comparison, horizon: int) -> pd.DataFrame:
    """Per-event (a, b) values of one metric; events missing either value are dropped."""
    sub = table[(table["horizon"] == horizon) & table["model"].isin([c.a, c.b])]
    wide = sub.pivot(index="event_id", columns="model", values=c.metric)
    return wide.reindex(columns=[c.a, c.b]).dropna()


def run_tests(table: pd.DataFrame) -> pd.DataFrame:
    horizons = sorted(int(h) for h in table["horizon"].unique())
    out = []
    for c in comparisons(set(table["model"])):
        if c.metric not in table.columns:
            continue
        family: list[dict[str, Any]] = []
        for h in horizons:
            w = paired(table, c, h)
            w = w[w[c.b] > 0]  # relative reduction undefined for a zero baseline error
            a, b = w[c.a].to_numpy(), w[c.b].to_numpy()
            rel = (b - a) / b
            med, lo, hi = bootstrap_ci(rel)
            family.append(
                {
                    "hypothesis": c.hypothesis,
                    "a": c.a,
                    "b": c.b,
                    "metric": c.metric,
                    "horizon": h,
                    "n_events": len(w),
                    "mean_a": float(np.mean(a)) if len(w) else math.nan,
                    "mean_b": float(np.mean(b)) if len(w) else math.nan,
                    "a_wins": int(np.sum(a < b)),
                    "p": wilcoxon_less(a, b) if len(w) else math.nan,
                    "median_rel_reduction": med,
                    "ci_low": lo,
                    "ci_high": hi,
                }
            )
        for row, p_adj in zip(family, holm([r["p"] for r in family]), strict=True):
            row["p_holm"] = p_adj
            row["significant"] = bool(p_adj < ALPHA)
            row["practical"] = bool(float(row["median_rel_reduction"]) >= PRACTICAL)
        out += family
    return pd.DataFrame(out)


def ranking(table: pd.DataFrame) -> pd.DataFrame:
    """Mean per-event MAE per horizon and model, and whether A4 <= A3 <= A1 holds (H6)."""
    mean = table.groupby(["horizon", "model"])["mae"].mean().unstack("model")
    need = {"xgb_A1", "xgb_A3", "xgb_A4"}
    if need <= set(mean.columns):
        mean["A4<=A3<=A1"] = (mean["xgb_A4"] <= mean["xgb_A3"]) & (mean["xgb_A3"] <= mean["xgb_A1"])
    return mean


def coverage_table(table: pd.DataFrame) -> pd.DataFrame:
    """H7: mean per-event conformal P10-P90 coverage with a bootstrap CI."""
    if "coverage_conformal" not in table.columns:
        return pd.DataFrame()
    rows = []
    q = table.dropna(subset=["coverage_conformal"])
    for (h, m), g in q.groupby(["horizon", "model"]):
        mean, lo, hi = bootstrap_ci(g["coverage_conformal"].to_numpy(), stat="mean")
        rows.append(
            {
                "horizon": h,
                "model": m,
                "n_events": len(g),
                "coverage": mean,
                "ci_low": lo,
                "ci_high": hi,
                "in_75_85": bool(COVERAGE_BAND[0] <= mean <= COVERAGE_BAND[1]),
                "width": float(g["width_conformal"].mean()),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------- report
def _md(df: pd.DataFrame, digits: int = 3) -> str:
    """Plain markdown table (no extra dependency)."""
    if df.empty:
        return "_none_\n"
    d = df.reset_index() if df.index.name or isinstance(df.index, pd.MultiIndex) else df

    def cell(x: object) -> str:
        if isinstance(x, float):
            return (
                "" if math.isnan(x) else f"{x:.{digits}g}" if abs(x) < 1e-3 else f"{x:.{digits}f}"
            )
        return str(x)

    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)]
    lines += ["| " + " | ".join(cell(x) for x in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join(lines) + "\n"


def report(run_dir: Path, commit: str) -> str:
    table = pd.read_csv(run_dir / "per_event.csv")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    tests = run_tests(table)
    rank = ranking(table)
    cov = coverage_table(table)
    tests.to_csv(run_dir / "statistics.csv", index=False)
    split = manifest.get("split", "?")
    banner = (
        "**VALIDATION split: development numbers, not hypothesis tests** (the tests are the "
        "test-split runs, evaluated once)."
        if split == "validation"
        else f"Test split `{split}` (final run: {manifest.get('final')})."
    )
    strata = table.groupby(["horizon", "model"])[
        [c for c in ("mae", "mae_peak", "mae_post_release") if c in table.columns]
    ].mean()
    text = (
        f"# Statistics for ablation run {manifest.get('run')}\n\n"
        f"Data: {manifest.get('data_origin')} - {manifest.get('data')}. Params: "
        f"{manifest.get('params', 'untuned')}. Ablation commit `{manifest.get('git_commit')}`; "
        f"statistics commit `{commit}`.\n\n{banner}\n\n"
        f"Method: one-sided Wilcoxon signed-rank over events (a < b), Holm across horizons "
        f"within each comparison (alpha {ALPHA}); effect = median per-event relative MAE "
        f"reduction (b - a) / b with 95 % bootstrap CI ({N_BOOT} resamples, seed {SEED}); "
        f"practical if >= {PRACTICAL:.0%}.\n\n"
        f"## Comparisons\n\n{_md(tests)}\n"
        f"## Mean per-event MAE (persons) and H6 ranking\n\n{_md(rank, 2)}\n"
        f"## Strata (mean per-event MAE; peak = true u >= 0.6, post-release = 30 min after an "
        f"upstream item ends)\n\n{_md(strata, 2)}\n"
        f"## H7 conformal coverage (nominal 0.80, band 0.75-0.85)\n\n{_md(cov)}"
    )
    (run_dir / "statistics.md").write_text(text, encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="runs/ablation/<run>")
    args = parser.parse_args(argv)
    commit = git_commit()
    if commit.endswith("(dirty working tree)"):
        print("uncommitted changes: commit first (results must come from committed code)")
        return 2
    print(report(args.run_dir.resolve(), commit))
    return 0


if __name__ == "__main__":
    sys.exit(main())

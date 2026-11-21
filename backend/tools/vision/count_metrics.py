"""Counting metrics by density band (doc 16 §2.1; WORKFLOW 7.1.2).

The public datasets have no calibrated areas, so bands use the TRUE count per image/region
(0-10, 11-30, 31-60, > 60), as doc 16 §2.1 allows - and every table must say so.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

COUNT_BANDS = ((0, 10, "0-10"), (11, 30, "11-30"), (31, 60, "31-60"), (61, None, ">60"))


def band_of(true_count: int) -> str:
    for lo, hi, name in COUNT_BANDS:
        if true_count >= lo and (hi is None or true_count <= hi):
            return name
    raise ValueError(f"negative count {true_count}")


@dataclass(frozen=True)
class CountMetrics:
    n: int
    mae: float
    rmse: float
    bias: float  # mean(pred - true): negative = undercount
    relative_mae: float  # sum|pred - true| / sum(true)
    mean_true: float


def count_metrics(true: Sequence[float], pred: Sequence[float]) -> CountMetrics:
    t = np.asarray(true, dtype=np.float64)
    p = np.asarray(pred, dtype=np.float64)
    if t.shape != p.shape or t.size == 0:
        raise ValueError("need two equally long, non-empty sequences")
    err = p - t
    return CountMetrics(
        n=int(t.size),
        mae=float(np.mean(np.abs(err))),
        rmse=float(np.sqrt(np.mean(err**2))),
        bias=float(np.mean(err)),
        relative_mae=float(np.sum(np.abs(err)) / np.sum(t)) if np.sum(t) > 0 else float("nan"),
        mean_true=float(np.mean(t)),
    )


def by_band(true: Sequence[int], pred: Sequence[float]) -> dict[str, CountMetrics]:
    """Metrics per count band plus "all"; bands without samples are left out."""
    out = {"all": count_metrics(true, pred)}
    for _, _, name in COUNT_BANDS:
        idx = [i for i, t in enumerate(true) if band_of(int(t)) == name]
        if idx:
            out[name] = count_metrics([true[i] for i in idx], [pred[i] for i in idx])
    return out

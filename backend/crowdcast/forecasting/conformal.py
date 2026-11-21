"""Split-conformal calibration of the P10-P90 interval (CQR; doc 10 §11; WORKFLOW 7.3.3).

Conformity score on calibration (validation) rows: E = max(q10 - y, y - q90), where y is the
actual occupancy. Scores are divided by the zone capacity, i.e. measured on the model's own
target scale (capacity-normalised change), so one offset per horizon fits zones of every size.
The offset Q is the ceil((n + 1)(1 - alpha))-th smallest score (the (1 - alpha)(1 + 1/n)
empirical quantile); the interval becomes [q10 - Q*C, q90 + Q*C]. Q < 0 narrows an
over-wide interval. Afterwards the lower bound is floored at 0 and the median is kept inside
the interval (the three quantiles never cross).

Exchangeability between calibration and new events is assumed, not guaranteed (time series,
synthetic-to-real shift), so coverage is always MEASURED on held-out events (doc 10 §11).
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from crowdcast.forecasting.features import Arr

ALPHA = 0.2  # nominal 80 % interval (P10-P90)


def conformity_scores(quantiles: Arr, actual: npt.ArrayLike, capacity: npt.ArrayLike) -> Arr:
    """(rows,) capacity-normalised CQR scores from (rows, 3) occupancy quantiles."""
    a = np.asarray(actual, dtype=np.float64)
    c = np.asarray(capacity, dtype=np.float64)
    e = np.maximum(quantiles[:, 0] - a, a - quantiles[:, 2])
    return np.asarray(e / c, dtype=np.float64)


def conformal_offset(scores: npt.ArrayLike, alpha: float = ALPHA) -> float:
    """Finite-sample split-conformal quantile; +inf if there are too few scores."""
    s = np.sort(np.asarray(scores, dtype=np.float64))
    n = len(s)
    k = math.ceil((n + 1) * (1 - alpha))
    if n == 0 or k > n:
        return math.inf
    return float(s[k - 1])


def apply_offset(quantiles: Arr, offset: float, capacity: npt.ArrayLike) -> Arr:
    """Widen (or narrow) the P10-P90 interval by offset * capacity; keep P50 inside it."""
    c = np.asarray(capacity, dtype=np.float64)
    q50 = quantiles[:, 1]
    lo = np.minimum(np.maximum(0.0, quantiles[:, 0] - offset * c), q50)
    hi = np.maximum(quantiles[:, 2] + offset * c, q50)
    return np.column_stack([lo, q50, hi])


def coverage(quantiles: Arr, actual: npt.ArrayLike) -> float:
    a = np.asarray(actual, dtype=np.float64)
    return float(np.mean((a >= quantiles[:, 0]) & (a <= quantiles[:, 2])))


def mean_width(quantiles: Arr) -> float:
    return float(np.mean(quantiles[:, 2] - quantiles[:, 0]))

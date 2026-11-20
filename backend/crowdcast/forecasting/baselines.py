"""Baselines B0-B3 (doc 10 §2, §3.2; WORKFLOW 4.1.1).

Every learned model is compared with all four at every horizon (CLAUDE.md §5).

Inputs are histories that END at the issue time t: row -1 is bucket t, row -2 is t-1, ...
(occupancy at the end of each bucket, flows during it - doc 10 §1.1). Arrays have shape
(L, Z): L buckets x Z zones; each function returns a (Z,) forecast of N(t + h).

Missing values (NaN) are handled without look-ahead: occupancy is forward-filled only
(doc 10 §7); missing flows are skipped. A zone with no occupancy value yet gives NaN.
Formulas are implemented exactly as specified: only B3 is clipped (to [0, 1.5 C]).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

HORIZONS = (5, 15, 30)  # minutes (doc 10 §1.2)
B1_WINDOW = 5  # k
B2_WINDOW = 10  # minutes for the OLS slope
B3_WINDOW = 5  # k for the mean net flow
B3_CAP_FACTOR = 1.5  # N_max = 1.5 C

Array = npt.NDArray[np.float64]


def _as_2d(x: npt.ArrayLike) -> Array:
    a = np.asarray(x, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    if a.ndim != 2 or a.shape[0] == 0:
        raise ValueError(f"history must have shape (L >= 1, Z), got {a.shape}")
    return a


def forward_fill(x: npt.ArrayLike) -> Array:
    """Fill NaNs with the last earlier value in the same column (never a later one)."""
    a = _as_2d(x).copy()
    for r in range(1, a.shape[0]):
        gap = np.isnan(a[r])
        a[r, gap] = a[r - 1, gap]
    return a


def b0_persistence(n: npt.ArrayLike, h: int) -> Array:
    """N_hat(t+h) = N(t)."""
    del h  # the forecast is the same for every horizon
    return np.asarray(forward_fill(n)[-1], dtype=np.float64).copy()


def b1_moving_average(n: npt.ArrayLike, h: int, k: int = B1_WINDOW) -> Array:
    """Mean of the last k values (fewer if the history is shorter)."""
    del h
    return np.asarray(forward_fill(n)[-k:].mean(axis=0), dtype=np.float64)


def b2_linear_trend(n: npt.ArrayLike, h: int, window: int = B2_WINDOW) -> Array:
    """N(t) + h * OLS slope over the last ``window`` minutes (slope 0 with one point)."""
    y = forward_fill(n)[-window:]
    m = y.shape[0]
    if m < 2:
        return np.asarray(y[-1], dtype=np.float64).copy()
    x = np.arange(m, dtype=np.float64) - (m - 1) / 2  # centred minutes
    slope = (x[:, None] * (y - y.mean(axis=0))).sum(axis=0) / (x**2).sum()
    return np.asarray(y[-1] + h * slope, dtype=np.float64)


def b3_conservation(
    n: npt.ArrayLike,
    inflow: npt.ArrayLike,
    outflow: npt.ArrayLike,
    capacity: npt.ArrayLike,
    h: int,
    k: int = B3_WINDOW,
    cap_factor: float = B3_CAP_FACTOR,
) -> Array:
    """clip(N(t) + h * mean net flow over the last k minutes, 0, 1.5 C) (doc 10 §3.2).

    Minutes whose inflow or outflow is missing are left out of the mean; with no usable
    minute the net flow is taken as 0 (= persistence).
    """
    current = forward_fill(n)[-1]
    net = (_as_2d(inflow) - _as_2d(outflow))[-k:]
    usable = ~np.isnan(net)
    count = usable.sum(axis=0)
    q = np.where(count > 0, np.where(usable, net, 0.0).sum(axis=0) / np.maximum(count, 1), 0.0)
    n_max = cap_factor * np.asarray(capacity, dtype=np.float64)
    return np.asarray(np.clip(current + h * q, 0.0, n_max), dtype=np.float64)


def all_baselines(
    n: npt.ArrayLike,
    inflow: npt.ArrayLike,
    outflow: npt.ArrayLike,
    capacity: npt.ArrayLike,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[str, Array]:
    """{"B0".."B3": array (len(horizons), Z)} - every baseline at every horizon."""
    return {
        "B0": np.stack([b0_persistence(n, h) for h in horizons]),
        "B1": np.stack([b1_moving_average(n, h) for h in horizons]),
        "B2": np.stack([b2_linear_trend(n, h) for h in horizons]),
        "B3": np.stack([b3_conservation(n, inflow, outflow, capacity, h) for h in horizons]),
    }

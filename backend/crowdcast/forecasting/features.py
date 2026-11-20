"""The one FeatureBuilder for training and the online cycle (doc 10 §5-7; WORKFLOW 5.1).

``build_features`` turns a per-minute history of one event into one feature row per
(bucket, zone). Every operation is causal - lags, right-closed windows, forward-fill only - so
the row for bucket k depends only on buckets <= k. Training calls it on a whole event; the
online cycle calls it on its last ``FEATURE_WINDOW`` minutes and keeps the final row. Tests
(TC-ML-02) check that both give identical values.

Conventions (doc 10 §1.1): row k is the bucket starting ``offset + k`` minutes after the event
start; N is occupancy at the END of that bucket, flows are crossings during it. The issue time
of row k is therefore ``offset + k + 1`` minutes after the start.

Deviations from doc 10 (logged in WORKFLOW.md):
- ``fused_u_t`` runs its recursion over a fixed 60-minute look-back for every row (not from
  the event start), so a 60-minute online window reproduces training exactly.
- ``nbr_flow_to_i`` is not built: per-connection flows are not stored by the ingestion
  contract. ``nbr_out_pressure`` uses zone outflows and shares estimated on training events.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import numpy.typing as npt
import pandas as pd

from crowdcast.common.enums import ScheduleCategory, ZoneType
from crowdcast.forecasting.baselines import b3_conservation, forward_fill

Arr = npt.NDArray[np.float64]

FEATURE_WINDOW = 60  # minutes of history the online cycle must pass (>= every lag/window)
U_LAGS = (1, 2, 3, 5, 10, 15, 30)
ROLL_WINDOWS = (5, 15)
SLOPE_WINDOW = 10
FLOW_LAGS = (0, 1, 2, 5)
NET_WINDOWS = (5, 15)
SCHED_CAP_MIN = 120.0
FUSION_ALPHA = 0.5  # doc 10 §3.4 default


class FeatureSet(StrEnum):
    """Ablation configurations (doc 10 §5.5; A5 = GNN extension, not built here)."""

    A1 = "A1"  # F_HIST
    A2 = "A2"  # F_HIST + F_FLOW
    A3 = "A3"  # F_HIST + F_SCHED
    A4 = "A4"  # F_HIST + F_FLOW + F_SCHED + F_NBR
    A4_NONBR = "A4_NONBR"  # A4 without F_NBR (isolates the neighbour features)


GROUPS: dict[FeatureSet, tuple[str, ...]] = {
    FeatureSet.A1: ("HIST",),
    FeatureSet.A2: ("HIST", "FLOW"),
    FeatureSet.A3: ("HIST", "SCHED"),
    FeatureSet.A4: ("HIST", "FLOW", "SCHED", "NBR"),
    FeatureSet.A4_NONBR: ("HIST", "FLOW", "SCHED"),
}


# ---------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class VenueInfo:
    """Static zone facts and graph matrices, zones in a fixed order (Z zones)."""

    codes: tuple[str, ...]
    capacity: Arr  # (Z,)
    area: Arr  # (Z,)
    zone_type: tuple[ZoneType, ...]
    is_entry: Arr  # (Z,) 0/1
    is_exit: Arr  # (Z,) 0/1
    adjacency: Arr  # (Z, Z) A[j, i] = 1 if j -> i (zones only, doc 11 §5.3)
    width: Arr  # (Z, Z) boundary width of j -> i, 0 if none
    travel_min: Arr  # (Z, Z) direct travel time of j -> i in minutes, 0 if none
    outflow_share: Arr  # (Z, Z) pi[j, i]: share of j's outflow going to i (training only)

    @property
    def degree(self) -> Arr:
        undirected = np.maximum(self.adjacency, self.adjacency.T)
        return np.asarray(undirected.sum(axis=0), dtype=np.float64)


@dataclass(frozen=True)
class SchedItem:
    """One PUBLISHED schedule item, in minutes since the event start."""

    zone: int | None  # zone index; None = venue-wide
    category: ScheduleCategory
    start_min: float
    end_min: float
    expected_attendance: float | None
    attraction: float


@dataclass(frozen=True)
class History:
    """Per-minute observations of one event (rows = buckets, cols = zones)."""

    n: Arr  # (L, Z) occupancy at bucket end; NaN = missing
    inflow: Arr  # (L, Z)
    outflow: Arr  # (L, Z)
    speed: Arr  # (L, Z) NaN when not measured
    offset: int  # minutes from event start to the first row's bucket start
    duration_min: float  # published event length
    schedule: Sequence[SchedItem] = field(default_factory=tuple)


# ---------------------------------------------------------------------- helpers (all causal)
def _shift(a: Arr, lag: int) -> Arr:
    out = np.full_like(a, np.nan)
    if lag < a.shape[0]:
        out[lag:] = a[: a.shape[0] - lag]
    return out


def _roll(a: Arr, k: int, fn: str) -> Arr:
    df = pd.DataFrame(a)
    r = df.rolling(k, min_periods=1 if fn == "mean" else 2)
    return np.asarray(r.mean() if fn == "mean" else r.std(ddof=0), dtype=np.float64)


def _roll_sum(a: Arr, k: int) -> Arr:
    return np.asarray(pd.DataFrame(a).rolling(k, min_periods=1).sum(), dtype=np.float64)


def _slope(a: Arr, k: int) -> Arr:
    """OLS slope per minute over the last k rows (fewer at the start; NaN with one row)."""
    out = np.full_like(a, np.nan)
    for r in range(1, a.shape[0]):
        y = a[max(0, r - k + 1) : r + 1]
        m = y.shape[0]
        x = np.arange(m, dtype=np.float64) - (m - 1) / 2
        ok = ~np.isnan(y)
        # an all-NaN column (zone without data in the window) legitimately gives NaN
        with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            num = np.where(ok, x[:, None] * (y - np.nanmean(y, axis=0)), 0.0).sum(axis=0)
            den = np.where(ok, x[:, None] ** 2, 0.0).sum(axis=0)
            out[r] = np.where(den > 0, num / den, np.nan)
    return out


def _fused(n: Arr, fin: Arr, fout: Arr, window: int = FEATURE_WINDOW) -> Arr:
    """Complementary filter (doc 10 §3.4) over a fixed look-back.

    For every row r the recursion starts afresh at row r - window + 1 (or 0), so the value at r
    is the same whether the input is the whole event or only its last ``window`` minutes.
    """
    out = np.full_like(n, np.nan)
    for r in range(n.shape[0]):
        lo = max(0, r - window + 1)
        est = n[lo].copy()
        for q in range(lo + 1, r + 1):
            ok = ~(np.isnan(fin[q]) | np.isnan(fout[q]) | np.isnan(est))
            integrated = est + np.nan_to_num(fin[q]) - np.nan_to_num(fout[q])
            est = np.where(ok, FUSION_ALPHA * n[q] + (1 - FUSION_ALPHA) * integrated, n[q])
        out[r] = est
    return out


# ---------------------------------------------------------------------- builder
def build_features(
    hist: History, venue: VenueInfo, feature_set: FeatureSet, horizon: int
) -> pd.DataFrame:
    """One row per (row k, zone) with the columns of ``feature_set`` for ``horizon`` minutes.

    Index columns: ``k`` (row in ``hist``), ``minute`` (issue time in minutes since start),
    ``zone``. Values for row k use only rows <= k of ``hist`` and the published schedule.
    """
    groups = GROUPS[feature_set]
    length, zones = hist.n.shape
    cap = venue.capacity[None, :]
    n = forward_fill(hist.n)  # forward-fill only (doc 10 §7)
    u = n / cap
    issue_min = hist.offset + np.arange(length, dtype=np.float64) + 1  # minutes since start
    cols: dict[str, Arr] = {}

    # ---- F_HIST (doc 10 §5.1)
    cols["u_t"] = u
    for lag in U_LAGS:
        cols[f"u_lag_{lag}"] = _shift(u, lag)
    for k in ROLL_WINDOWS:
        cols[f"u_roll_mean_{k}"] = _roll(u, k, "mean")
        cols[f"u_roll_std_{k}"] = _roll(u, k, "std")
    cols["u_slope_10"] = _slope(u, SLOPE_WINDOW)
    cols["n_t"] = n
    cols["fused_u_t"] = _fused(n, hist.inflow, hist.outflow) / cap
    ones = np.ones((length, 1))
    for zt in ZoneType:
        cols[f"zone_type_{zt.value}"] = ones * np.array(
            [1.0 if t is zt else 0.0 for t in venue.zone_type]
        )
    cols["capacity"] = ones * venue.capacity
    cols["area"] = ones * venue.area
    cols["is_entry"] = ones * venue.is_entry
    cols["is_exit"] = ones * venue.is_exit
    cols["degree"] = ones * venue.degree
    cols["minutes_since_start"] = issue_min[:, None] * np.ones((1, zones))
    cols["minutes_to_end"] = (hist.duration_min - issue_min)[:, None] * np.ones((1, zones))
    cols["frac_elapsed"] = (issue_min / hist.duration_min)[:, None] * np.ones((1, zones))

    # ---- F_FLOW (doc 10 §5.2)
    if "FLOW" in groups:
        for lag in FLOW_LAGS:
            cols[f"fin_lag_{lag}"] = _shift(hist.inflow, lag) / cap
            cols[f"fout_lag_{lag}"] = _shift(hist.outflow, lag) / cap
        net = hist.inflow - hist.outflow
        for k in NET_WINDOWS:
            cols[f"net_sum_{k}"] = _roll_sum(net, k) / cap
        b3 = np.full((length, zones), np.nan)
        for r in range(length):
            lo = max(0, r - 4)
            b3[r] = b3_conservation(
                n[: r + 1], hist.inflow[lo : r + 1], hist.outflow[lo : r + 1],
                venue.capacity, horizon,
            )  # fmt: skip
        cols["b3_pred_h"] = (b3 - n) / cap  # same scale as the target
        cols["speed_t"] = hist.speed
        cols["speed_roll_5"] = _roll(hist.speed, 5, "mean")

    # ---- F_SCHED (doc 10 §5.3) - published schedule only
    if "SCHED" in groups or "NBR" in groups:
        sched = _schedule_features(hist.schedule, issue_min, zones, venue.capacity, horizon)
        if "SCHED" in groups:
            cols.update(sched)

    # ---- F_NBR (doc 10 §5.4)
    if "NBR" in groups:
        cols.update(_neighbour_features(u, hist.outflow, venue, sched["ends_within_h"], cap))

    rows = pd.DataFrame(
        {name: np.asarray(v, dtype=np.float64).reshape(-1) for name, v in cols.items()}
    )
    rows.insert(0, "zone", np.tile(np.arange(zones), length))
    rows.insert(0, "minute", np.repeat(issue_min, zones))
    rows.insert(0, "k", np.repeat(np.arange(length), zones))
    return rows


def _schedule_features(
    items: Sequence[SchedItem], issue_min: Arr, zones: int, capacity: Arr, horizon: int
) -> dict[str, Arr]:
    length = issue_min.shape[0]
    t = issue_min[:, None]  # (L, 1)
    out: dict[str, Arr] = {
        "active_item": np.zeros((length, zones)),
        "min_to_next_start": np.full((length, zones), SCHED_CAP_MIN),
        "min_since_last_end": np.full((length, zones), SCHED_CAP_MIN),
        "min_to_next_end": np.full((length, zones), np.nan),
        "next_item_attendance": np.zeros((length, zones)),
        "attraction": np.zeros((length, zones)),
        "starts_within_h": np.zeros((length, zones)),
        "ends_within_h": np.zeros((length, zones)),
    }
    for c in ScheduleCategory:
        out[f"active_category_{c.value}"] = np.zeros((length, zones))
    venue_ending = np.zeros((length, 1))

    for z in range(zones):
        mine = [it for it in items if it.zone == z]
        best_next = np.full(length, np.inf)
        for it in mine:
            s, e = it.start_min, it.end_min
            active = (t[:, 0] >= s) & (t[:, 0] < e)
            out["active_item"][:, z] = np.maximum(out["active_item"][:, z], active)
            out[f"active_category_{it.category.value}"][:, z] = np.maximum(
                out[f"active_category_{it.category.value}"][:, z], active
            )
            ahead = s - t[:, 0]
            upcoming = ahead > 0
            out["min_to_next_start"][:, z] = np.where(
                upcoming,
                np.minimum(out["min_to_next_start"][:, z], ahead),
                out["min_to_next_start"][:, z],
            )
            since = t[:, 0] - e
            ended = since >= 0
            out["min_since_last_end"][:, z] = np.where(
                ended,
                np.minimum(out["min_since_last_end"][:, z], since),
                out["min_since_last_end"][:, z],
            )
            out["min_to_next_end"][:, z] = np.where(
                active,
                np.fmin(out["min_to_next_end"][:, z], e - t[:, 0]),
                out["min_to_next_end"][:, z],
            )
            # attendance / attraction of the active item, else of the next one to start
            rank = np.where(active, -1.0, np.where(upcoming, ahead, np.inf))
            better = rank < best_next
            best_next = np.where(better, rank, best_next)
            att = 0.0 if it.expected_attendance is None else it.expected_attendance / capacity[z]
            out["next_item_attendance"][:, z] = np.where(
                better, att, out["next_item_attendance"][:, z]
            )
            out["attraction"][:, z] = np.where(better, it.attraction, out["attraction"][:, z])
            out["starts_within_h"][:, z] = np.maximum(
                out["starts_within_h"][:, z], (s > t[:, 0]) & (s <= t[:, 0] + horizon)
            )
            out["ends_within_h"][:, z] = np.maximum(
                out["ends_within_h"][:, z], (e > t[:, 0]) & (e <= t[:, 0] + horizon)
            )
        out["min_to_next_start"][:, z] = np.minimum(out["min_to_next_start"][:, z], SCHED_CAP_MIN)
        out["min_since_last_end"][:, z] = np.minimum(out["min_since_last_end"][:, z], SCHED_CAP_MIN)
    for it in items:
        venue_ending[:, 0] += (it.end_min > t[:, 0]) & (it.end_min <= t[:, 0] + horizon)
    out["venue_items_ending_within_h"] = venue_ending * np.ones((1, zones))
    return out


def _neighbour_features(
    u: Arr, outflow: Arr, venue: VenueInfo, ends_within_h: Arr, cap: Arr
) -> dict[str, Arr]:
    length, zones = u.shape
    a = venue.adjacency
    nbr = np.maximum(a, a.T)  # neighbours in either direction
    w = np.maximum(venue.width, venue.width.T)
    slope = _slope(u, SLOPE_WINDOW)
    out = {
        "nbr_u_mean": np.full((length, zones), np.nan),
        "nbr_u_max": np.full((length, zones), np.nan),
        "nbr_u_wmean": np.full((length, zones), np.nan),
        "nbr_out_pressure": np.full((length, zones), np.nan),
        "nbr_u_slope": np.full((length, zones), np.nan),
        "nbr_sched_release_within_h": np.zeros((length, zones)),
        "nbr_lagged_u_tau": np.full((length, zones), np.nan),
    }
    for i in range(zones):
        js = np.flatnonzero(nbr[:, i] > 0)
        ups = np.flatnonzero(a[:, i] > 0)  # upstream: j -> i
        if len(js):
            # all-NaN slices (e.g. no slope yet in the first minute) legitimately give NaN
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out["nbr_u_mean"][:, i] = np.nanmean(u[:, js], axis=1)
                out["nbr_u_max"][:, i] = np.nanmax(u[:, js], axis=1)
                ww = w[js, i]
                out["nbr_u_wmean"][:, i] = (u[:, js] * ww).sum(axis=1) / ww.sum()
                out["nbr_u_slope"][:, i] = np.nanmean(slope[:, js], axis=1)
        if len(ups):
            share = venue.outflow_share[ups, i]
            out["nbr_out_pressure"][:, i] = (np.nan_to_num(outflow[:, ups]) * share).sum(
                axis=1
            ) / cap[0, i]
            out["nbr_sched_release_within_h"][:, i] = ends_within_h[:, ups].max(axis=1)
            lagged = np.column_stack(
                [_shift(u[:, [j]], int(np.floor(venue.travel_min[j, i])))[:, 0] for j in ups]
            )
            with np.errstate(all="ignore"), warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out["nbr_lagged_u_tau"][:, i] = np.nanmean(lagged, axis=1)
    return out


def add_target(rows: pd.DataFrame, hist: History, venue: VenueInfo, horizon: int) -> pd.DataFrame:
    """y = (N(t+h) - N(t)) / C (doc 10 §6); rows whose target lies beyond the data are dropped.

    For training only: the target uses the TRUE future occupancy of the same event.
    """
    n = forward_fill(hist.n)
    length = n.shape[0]
    k = rows["k"].to_numpy()
    z = rows["zone"].to_numpy()
    keep = (k + horizon) < length
    future = np.full(len(rows), np.nan)
    future[keep] = n[k[keep] + horizon, z[keep]]
    y = (future - n[k, z]) / venue.capacity[z]
    out = rows.assign(y=y)
    kept: pd.DataFrame = out[keep & ~np.isnan(y)].reset_index(drop=True)
    return kept


def feature_columns(rows: pd.DataFrame) -> list[str]:
    return [c for c in rows.columns if c not in ("k", "minute", "zone", "y")]

"""Congestion classification and operational (alert-level) evaluation of an ablation run
(WORKFLOW 7.4.1, 7.4.2; doc 16 §4-5; objectives O5, O6).

Input: runs/ablation/<run>/predictions.parquet (per-row P50 and conformal P10/P90 per model and
horizon) and the TRUE simulator occupancy of each event (SYN-clean history, also for SYN-noisy
runs, whose inputs - and therefore CURRENT alerts - are noisy).

Classification (doc 16 §4), per horizon and model, pooled over the split's rows:
positive = true level >= HIGH at t + h; prediction = L(P50 / C) >= HIGH. Precision, recall, F1
(with a 95 % bootstrap CI over events), the 4 x 4 level confusion matrix, and a PR curve over
an absolute threshold tau on P50 / C and on P90 / C.

Operational (doc 16 §5): every event is replayed minute by minute through the REAL alert state
machine ``crowdcast.risk.alerts.decide`` (2-cycle PREDICTED confirmation, hysteresis, CRITICAL
escalation), once per model, with CURRENT from the observed occupancy N(t) and PREDICTED from
the model's P50 at 5/15/30 min. The database wrapper (risk/engine.py) is not used: it only
stores what ``decide`` returns (Deviation log).

- Episode: maximal run of >= 2 minutes with true u >= theta_HIGH; onset t_on.
- An alert covers an episode if it opens in the same zone within [t_on - 35, t_on + 2] min;
  lead time = t_on - t_alert of the earliest covering alert (negative = late).
- False alarm: no episode in the zone is ongoing at t_alert or starts within h + 5 min after
  it (h = 0 for CURRENT).

Usage (from backend/, clean tree):
  uv run python -m tools.training.operational ../runs/ablation/<run>
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

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.enums import AlertType, CongestionLevel
from crowdcast.forecasting.baselines import forward_fill
from crowdcast.forecasting.sources import venue_info
from crowdcast.risk.alerts import RESOLVE_CYCLES, Action, CycleSignal, decide
from crowdcast.risk.levels import LEVEL_ORDER, Thresholds
from crowdcast.venue_graph.interfaces import load_venue_config
from tools.training.dataset import load_history
from tools.training.stats import N_BOOT, SEED
from tools.training.train import git_commit

COVER_BEFORE = 35  # minutes before onset an alert may open and still cover it (doc 16 §5)
COVER_AFTER = 2
FALSE_ALARM_SLACK = 5  # alert must be followed by an episode within h + 5 min
EPISODE_MIN = 2
PR_TAUS = np.round(np.arange(0.50, 1.201, 0.05), 2)


# ---------------------------------------------------------------------- venue thresholds
@dataclass(frozen=True)
class VenueThresholds:
    codes: tuple[str, ...]
    capacity: np.ndarray
    thresholds: tuple[Thresholds, ...]  # per zone, in ``codes`` order

    def arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(elevated, high, critical) per zone."""
        t = self.thresholds
        return (
            np.array([x.elevated for x in t]),
            np.array([x.high for x in t]),
            np.array([x.critical for x in t]),
        )


def venue_thresholds(venue: str) -> VenueThresholds:
    cfg = load_venue_config(REPO_ROOT / "configs" / "venues" / f"{venue}.yaml")
    info = venue_info(cfg)
    by_code = {z.code: Thresholds(*z.thresholds.resolved()) for z in cfg.zones}
    return VenueThresholds(info.codes, info.capacity, tuple(by_code[c] for c in info.codes))


def level_index(u: np.ndarray, e: np.ndarray, h: np.ndarray, c: np.ndarray) -> np.ndarray:
    """0 NORMAL, 1 ELEVATED, 2 HIGH, 3 CRITICAL (lower bounds inclusive, as risk.levels)."""
    out: np.ndarray = (u >= e).astype(int) + (u >= h).astype(int) + (u >= c).astype(int)
    return out


# ---------------------------------------------------------------------- classification
def prf(tp: float, fp: float, fn: float) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else math.nan
    r = tp / (tp + fn) if tp + fn else math.nan
    f = 2 * p * r / (p + r) if (p + r) and not (math.isnan(p) or math.isnan(r)) else math.nan
    return p, r, f


def f1_ci(counts: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float]:
    """95 % percentile bootstrap CI of the pooled F1, resampling events (rows of ``counts``
    with columns tp, fp, fn)."""
    c = counts[["tp", "fp", "fn"]].to_numpy(dtype=np.float64)
    if len(c) == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    s = c[rng.integers(0, len(c), size=(n_boot, len(c)))].sum(axis=1)
    tp, fp, fn = s[:, 0], s[:, 1], s[:, 2]
    with np.errstate(invalid="ignore", divide="ignore"):
        f = 2 * tp / (2 * tp + fp + fn)
    lo, hi = np.nanpercentile(f, [2.5, 97.5])
    return float(lo), float(hi)


def classification(pred: pd.DataFrame, venues: dict[str, VenueThresholds]) -> dict[str, Any]:
    """Per (horizon, model): P/R/F1 (+ CI), confusion matrix and PR curve points."""
    e, h, c = (np.empty(len(pred)) for _ in range(3))
    for v, idx in pred.groupby("venue").indices.items():
        ev, hv, cv = venues[str(v)].arrays()
        z = pred["zone"].to_numpy()[idx]
        e[idx], h[idx], c[idx] = ev[z], hv[z], cv[z]
    cap = pred["capacity"].to_numpy(np.float64)
    u_true = pred["actual"].to_numpy(np.float64) / cap
    u50 = pred["p50"].to_numpy(np.float64) / cap
    u90 = pred["p90"].to_numpy(np.float64) / cap
    true_lvl = level_index(u_true, e, h, c)
    pred_lvl = level_index(u50, e, h, c)
    pos = true_lvl >= 2
    hat = pred_lvl >= 2

    summary, confusion, curve = [], [], []
    for key, idx in pred.groupby(["horizon", "model"]).indices.items():
        hz, model = int(key[0]), str(key[1])  # type: ignore[index]
        df = pd.DataFrame(
            {"event_id": pred["event_id"].to_numpy()[idx], "tp": pos[idx] & hat[idx],
             "fp": ~pos[idx] & hat[idx], "fn": pos[idx] & ~hat[idx]}
        )  # fmt: skip
        per_event = df.groupby("event_id")[["tp", "fp", "fn"]].sum()
        tp, fp, fn = (float(per_event[k].sum()) for k in ("tp", "fp", "fn"))
        p, r, f = prf(tp, fp, fn)
        lo, hi = f1_ci(per_event)
        summary.append(
            {"horizon": int(hz), "model": model, "rows": len(idx), "positives": int(pos[idx].sum()),
             "tp": int(tp), "fp": int(fp), "fn": int(fn), "precision": p, "recall": r, "f1": f,
             "f1_ci_low": lo, "f1_ci_high": hi}
        )  # fmt: skip
        m = np.zeros((4, 4), dtype=int)
        np.add.at(m, (true_lvl[idx], pred_lvl[idx]), 1)
        for i, t_name in enumerate(LEVEL_ORDER):
            for j, p_name in enumerate(LEVEL_ORDER):
                confusion.append(
                    {"horizon": int(hz), "model": model, "true": t_name.value,
                     "predicted": p_name.value, "count": int(m[i, j])}
                )  # fmt: skip
        for q, u in (("p50", u50), ("p90", u90)):
            uq = u[idx]
            if np.all(np.isnan(uq)):
                continue  # baselines have no P90
            for tau in PR_TAUS:
                pt = uq >= tau
                cp, cr, cf = prf(
                    float(np.sum(pos[idx] & pt)),
                    float(np.sum(~pos[idx] & pt)),
                    float(np.sum(pos[idx] & ~pt)),
                )
                curve.append(
                    {"horizon": int(hz), "model": model, "quantile": q, "tau": float(tau),
                     "precision": cp, "recall": cr, "f1": cf}
                )  # fmt: skip
    return {
        "summary": pd.DataFrame(summary),
        "confusion": pd.DataFrame(confusion),
        "pr_curve": pd.DataFrame(curve),
    }


# ---------------------------------------------------------------------- episodes and replay
@dataclass(frozen=True)
class Episode:
    zone: int
    onset: int  # k of the first minute at >= HIGH
    end: int  # k of the last minute at >= HIGH


@dataclass(frozen=True)
class Alert:
    zone: int
    kind: AlertType
    opened: int  # k
    horizon: int  # 0 for CURRENT


def episodes(u_true: np.ndarray, high: np.ndarray, min_len: int = EPISODE_MIN) -> list[Episode]:
    """Maximal runs of >= ``min_len`` minutes with true u >= theta_HIGH, per zone.
    ``u_true`` is (minutes, zones); NaN counts as below."""
    out = []
    above = np.nan_to_num(u_true, nan=-1.0) >= high[None, :]
    for z in range(above.shape[1]):
        a = np.concatenate([[False], above[:, z], [False]]).astype(np.int8)
        d = np.diff(a)
        for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1), strict=True):
            if e - s >= min_len:
                out.append(Episode(z, int(s), int(e - 1)))
    return out


def replay(
    current_u: np.ndarray, forecast_u: dict[int, np.ndarray], thresholds: tuple[Thresholds, ...]
) -> list[Alert]:
    """Run the M7 state machine over one event: ``current_u`` (minutes, zones), forecast_u
    {h: (minutes, zones)} median forecast ratio (NaN = no forecast for that minute)."""
    minutes, zones = current_u.shape
    alerts = []
    for z in range(zones):
        signals: list[CycleSignal] = []
        open_level: dict[AlertType, CongestionLevel | None] = {
            AlertType.CURRENT: None,
            AlertType.PREDICTED: None,
        }
        for k in range(minutes):
            cu = current_u[k, z]
            fu = {h: float(a[k, z]) for h, a in forecast_u.items() if not np.isnan(a[k, z])}
            signals.append(CycleSignal(None if np.isnan(cu) else float(cu), fu or None))
            history = signals[-RESOLVE_CYCLES:]
            for kind in (AlertType.CURRENT, AlertType.PREDICTED):
                d = decide(kind, history, open_level[kind], thresholds[z])
                if d.action is Action.OPEN:
                    open_level[kind] = d.level
                    alerts.append(Alert(z, kind, k, d.horizon_min or 0))
                elif d.action is Action.ESCALATE:
                    open_level[kind] = CongestionLevel.CRITICAL
                elif d.action is Action.RESOLVE:
                    open_level[kind] = None
    return alerts


def score_alerts(
    eps: list[Episode], alerts: list[Alert]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Per-episode (covered, lead time, source) and per-alert (false alarm) records."""
    ep_rows = []
    for ep in eps:
        cover = [
            a for a in alerts
            if a.zone == ep.zone and ep.onset - COVER_BEFORE <= a.opened <= ep.onset + COVER_AFTER
        ]  # fmt: skip
        first = min(cover, key=lambda a: (a.opened, a.kind != AlertType.CURRENT), default=None)
        ep_rows.append(
            {"zone": ep.zone, "onset": ep.onset, "duration": ep.end - ep.onset + 1,
             "covered": first is not None,
             "lead_time": math.nan if first is None else float(ep.onset - first.opened),
             "source": "missed" if first is None
             else "CURRENT" if first.kind is AlertType.CURRENT else f"P{first.horizon}"}
        )  # fmt: skip
    al_rows = []
    for a in alerts:
        horizon = a.horizon if a.kind is AlertType.PREDICTED else 0
        hit = any(
            ep.zone == a.zone
            and ep.end >= a.opened
            and ep.onset <= a.opened + horizon + FALSE_ALARM_SLACK
            for ep in eps
        )
        al_rows.append(
            {"zone": a.zone, "kind": a.kind.value, "horizon": horizon, "opened": a.opened,
             "false_alarm": not hit}
        )  # fmt: skip
    return ep_rows, al_rows


def event_arrays(pred_event: pd.DataFrame, zones: int) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """(current_u, {h: forecast_u}) on the event's minute axis k for ONE model."""
    minutes = int(pred_event["k"].max()) + 1
    cap = np.zeros(zones)
    cur = np.full((minutes, zones), np.nan)
    fc: dict[int, np.ndarray] = {}
    hz = pred_event["horizon"].to_numpy()
    for h in sorted(set(hz.tolist())):
        g = pred_event[hz == h]
        k, z = g["k"].to_numpy(), g["zone"].to_numpy()
        cap[z] = g["capacity"].to_numpy()
        cur[k, z] = g["n_t"].to_numpy() / cap[z]
        a = np.full((minutes, zones), np.nan)
        a[k, z] = g["p50"].to_numpy() / cap[z]
        fc[int(h)] = a
    return cur, fc


def operational(
    pred: pd.DataFrame, venues: dict[str, VenueThresholds], truth: dict[str, np.ndarray]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Replays every (event, model); returns (per-episode, per-alert, per-event) tables.
    ``truth[event_id]`` = TRUE occupancy (minutes, zones) on the k axis."""
    ep_all, al_all, ev_all = [], [], []
    for (eid, model), g in pred.groupby(["event_id", "model"]):
        vt = venues[str(g["venue"].iloc[0])]
        zones = len(vt.codes)
        cur, fc = event_arrays(g, zones)
        n_true = truth[str(eid)][: cur.shape[0]]
        eps = episodes(n_true / vt.capacity[None, :], vt.arrays()[1])
        ep_rows, al_rows = score_alerts(eps, replay(cur, fc, vt.thresholds))
        hours = cur.shape[0] / 60
        for r in ep_rows:
            r.update(event_id=eid, model=model)
        for r in al_rows:
            r.update(event_id=eid, model=model)
        ep_all += ep_rows
        al_all += al_rows
        leads = [r["lead_time"] for r in ep_rows if r["covered"]]
        fa = sum(r["false_alarm"] for r in al_rows)
        ev_all.append(
            {"event_id": eid, "model": model, "hours": hours, "episodes": len(ep_rows),
             "missed": sum(not r["covered"] for r in ep_rows), "alerts": len(al_rows),
             "false_alarms": fa, "median_lead_time": float(np.median(leads)) if leads else math.nan,
             "false_alarms_per_hour": fa / hours if hours else math.nan}
        )  # fmt: skip
    return pd.DataFrame(ep_all), pd.DataFrame(al_all), pd.DataFrame(ev_all)


def operational_summary(ep: pd.DataFrame, al: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, e in ev.groupby("model"):
        eps = ep[ep["model"] == model] if len(ep) else ep
        als = al[al["model"] == model] if len(al) else al
        lead = eps.loc[eps["covered"], "lead_time"] if len(eps) else pd.Series(dtype=float)
        src = eps["source"].value_counts(normalize=True) if len(eps) else pd.Series(dtype=float)
        rows.append(
            {"model": model, "events": len(e), "episodes": int(e["episodes"].sum()),
             "lead_median": float(lead.median()) if len(lead) else math.nan,
             "lead_q25": float(lead.quantile(0.25)) if len(lead) else math.nan,
             "lead_q75": float(lead.quantile(0.75)) if len(lead) else math.nan,
             "missed_rate": float(e["missed"].sum() / e["episodes"].sum())
             if e["episodes"].sum() else math.nan,
             "alerts": int(e["alerts"].sum()),
             "false_alarm_rate": float(als["false_alarm"].mean()) if len(als) else math.nan,
             "false_alarms_per_hour": float(e["false_alarms"].sum() / e["hours"].sum()),
             **{f"first_{s}": float(src.get(s, 0.0))
                for s in ("P30", "P15", "P5", "CURRENT", "missed")}}
        )  # fmt: skip
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------- runner
def true_occupancy(event_ids: list[str], venues: dict[str, VenueThresholds]) -> dict[str, Any]:
    out = {}
    for eid in event_ids:
        codes = venues[eid.split("_")[0]].codes
        out[eid] = forward_fill(load_history(eid, codes, variant="clean").n)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="runs/ablation/<run>")
    args = parser.parse_args(argv)
    commit = git_commit()
    if commit.endswith("(dirty working tree)"):
        print("uncommitted changes: commit first (results must come from committed code)")
        return 2
    run = args.run_dir.resolve()
    pred = pd.read_parquet(run / "predictions.parquet")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    venues = {v: venue_thresholds(v) for v in sorted(pred["venue"].unique())}
    cls = classification(pred, venues)
    truth = true_occupancy(sorted(pred["event_id"].unique()), venues)
    ep, al, ev = operational(pred, venues, truth)
    summary = operational_summary(ep, al, ev)
    cls["summary"].to_csv(run / "classification.csv", index=False)
    cls["confusion"].to_csv(run / "confusion.csv", index=False)
    cls["pr_curve"].to_csv(run / "pr_curve.csv", index=False)
    ep.to_csv(run / "episodes.csv", index=False)
    al.to_csv(run / "alerts.csv", index=False)
    ev.to_csv(run / "operational_per_event.csv", index=False)
    summary.to_csv(run / "operational.csv", index=False)
    (run / "operational_manifest.json").write_text(
        json.dumps(
            {"ablation_run": manifest.get("run"), "split": manifest.get("split"),
             "data": manifest.get("data"), "data_origin": manifest.get("data_origin"),
             "git_commit": commit, "cover_window": [-COVER_BEFORE, COVER_AFTER],
             "false_alarm_slack": FALSE_ALARM_SLACK, "episode_min": EPISODE_MIN},
            indent=1,
        ),
        encoding="utf-8",
    )  # fmt: skip
    pd.set_option("display.width", 200)
    print(f"split {manifest.get('split')} - {manifest.get('data')}")
    print(cls["summary"][["horizon", "model", "positives", "precision", "recall", "f1"]].round(3))
    print(summary.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

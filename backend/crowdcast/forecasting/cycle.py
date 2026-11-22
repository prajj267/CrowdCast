"""One prediction cycle (doc 10 §12; WORKFLOW 4.2.1-4.2.3).

``run_cycle(session, event_id, issued_at)`` forecasts every zone at +5/+15/+30 min and writes
``predictions``. ``issued_at`` is a minute boundary in **event time**: the cycle sees only the
buckets that ended by then (bucket_start < issued_at), so replays at any speed-up and
back-fills produce the same predictions as a live run (no wall-clock time anywhere).

Model choice: the active learned model (``model_versions.is_active``) forecasts each zone. With
no active model, during a cold start (< 15 min of history) or on any model failure, the zone
gets the B0 persistence fallback (``is_fallback = true``, logged). Persistence has no spread, so
p10 = p50 = p90 (no uncertainty is invented).

Data separation (CLAUDE.md §6): a synthetic event is forecast from SYNTHETIC observations,
any other event from REAL ones; MANUAL counts are ground truth, never model input here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import numpy.typing as npt
from sqlalchemy.orm import Session

from crowdcast.common.config import REPO_ROOT
from crowdcast.common.enums import DataOrigin
from crowdcast.common.time import ensure_utc, is_minute_aligned
from crowdcast.forecasting.baselines import HORIZONS, b0_persistence, forward_fill
from crowdcast.forecasting.features import History, SchedItem, build_features
from crowdcast.forecasting.sources import ConnectionRow, ZoneRow, venue_info_from_rows
from crowdcast.forecasting.xgb import QuantileForecaster, load_model
from crowdcast.risk.interfaces import AlertChanges, Thresholds, evaluate_alerts, level, risk_score
from crowdcast.storage.interfaces import Event, ModelVersion, Zone, repository
from crowdcast.venue_graph.interfaces import OUTSIDE

log = logging.getLogger("crowdcast.forecasting")

WINDOW_MIN = 60  # history the cycle reads (doc 10 §12)
MAX_GAP_MIN = 3  # forward-fill gaps up to 3 min; staler zones get no prediction
COLD_START_MIN = 15  # learned models need >= 15 min of history


@dataclass
class CycleResult:
    event_id: int
    issued_at: datetime
    written: int = 0
    fallback_zones: list[str] = field(default_factory=list)
    skipped_zones: dict[str, str] = field(default_factory=dict)  # code -> reason
    alerts: AlertChanges = field(default_factory=AlertChanges)
    model_zones: list[str] = field(default_factory=list)
    fallback_reason: str | None = None


def origin_for(is_synthetic: bool) -> DataOrigin:
    return DataOrigin.SYNTHETIC if is_synthetic else DataOrigin.REAL


def run_cycle(session: Session, event_id: int, issued_at: datetime) -> CycleResult:
    issued_at = ensure_utc(issued_at)
    if not is_minute_aligned(issued_at):
        raise ValueError(f"issued_at must be a minute boundary: {issued_at}")
    event = repository.get_event(session, event_id)
    if event is None:
        raise LookupError(f"event {event_id} not found")

    result = CycleResult(event_id, issued_at)
    zones = repository.list_zones(session, event.venue_id)
    col = {z.zone_id: k for k, z in enumerate(zones)}
    start = issued_at - timedelta(minutes=WINDOW_MIN)
    obs = repository.observation_window(
        session, event_id, origin_for(event.is_synthetic), start, issued_at
    )

    # (WINDOW_MIN, Z) series, NaN where no observation; row -1 = the bucket that just ended
    shape = (WINDOW_MIN, len(zones))
    n, fin, fout, speed = (np.full(shape, np.nan) for _ in range(4))
    for o in obs:
        row = int((ensure_utc(o.bucket_start) - start) / timedelta(minutes=1))
        c = col[o.zone_id]
        n[row, c] = np.nan if o.occupancy is None else o.occupancy
        fin[row, c] = np.nan if o.inflow is None else o.inflow
        fout[row, c] = np.nan if o.outflow is None else o.outflow
        speed[row, c] = np.nan if o.mean_speed_mps is None else o.mean_speed_mps

    # The active learned model, else (no model, cold start, any failure) the B0 fallback.
    model_q: dict[int, npt.NDArray[np.float64]] | None = None
    model_id = repository.baseline_model_version(session)
    active = repository.active_model_version(session)
    minutes_in = (issued_at - ensure_utc(event.start_time)) / timedelta(minutes=1)
    if active is not None and active.model_family == "XGBOOST":
        if minutes_in < COLD_START_MIN:
            result.fallback_reason = f"cold start ({minutes_in:.0f} min < {COLD_START_MIN})"
        else:
            try:
                model_q = _model_quantiles(
                    session, event, zones, start, n, fin, fout, speed, active
                )
                model_id = active.model_version_id
            except Exception as exc:  # any model failure falls back to B0 (doc 10 §12)
                result.fallback_reason = f"model {active.name}/{active.version} failed: {exc}"
                log.exception("model failed; using B0 fallback")
    elif active is not None:
        result.fallback_reason = f"model family {active.model_family} not supported online"

    filled = forward_fill(n)
    rows = []
    for k, z in enumerate(zones):
        seen = np.flatnonzero(~np.isnan(n[:, k]))
        if len(seen) == 0:
            result.skipped_zones[z.code] = "no observation in the last 60 min"
            continue
        age = WINDOW_MIN - 1 - int(seen[-1])  # minutes since the latest observed bucket
        if age > MAX_GAP_MIN:
            result.skipped_zones[z.code] = f"latest observation {age} min old (> {MAX_GAP_MIN})"
            continue
        thresholds = Thresholds.from_overrides(
            z.threshold_elevated, z.threshold_high, z.threshold_critical
        )
        capacity = float(z.planning_capacity)
        for h in HORIZONS:
            if model_q is not None:
                p10, p50, p90 = (float(v) for v in model_q[h][k])
            else:
                p10 = p50 = p90 = float(b0_persistence(filled[:, k], h)[0])
            rows.append(
                {
                    "event_id": event_id,
                    "zone_id": z.zone_id,
                    "issued_at": issued_at,
                    "horizon_min": h,
                    "target_time": issued_at + timedelta(minutes=h),
                    "p10": p10,
                    "p50": p50,
                    "p90": p90,
                    "predicted_level": level(p50 / capacity, thresholds),
                    "risk_score": risk_score(p50 / capacity, p90 / capacity, thresholds),
                    "model_version_id": model_id,
                    "is_fallback": model_q is None,
                }
            )
        (result.model_zones if model_q is not None else result.fallback_zones).append(z.code)

    result.written = repository.upsert_predictions(session, rows)
    # doc 10 §12: write predictions, then call the risk engine (M7)
    result.alerts = evaluate_alerts(session, event_id, issued_at, origin_for(event.is_synthetic))
    if result.fallback_zones:
        log.info(
            "event %s @ %s: B0 fallback for %d zones (%s)%s",
            event_id,
            issued_at.isoformat(),
            len(result.fallback_zones),
            result.fallback_reason or "no active model",
            f"; skipped {result.skipped_zones}" if result.skipped_zones else "",
        )
    return result


# ---------------------------------------------------------------------- learned model (5.3.3)
_LOADED: dict[int, QuantileForecaster] = {}


def _forecaster(mv: ModelVersion) -> QuantileForecaster:
    """Load a model directory once per process (models are immutable once registered)."""
    if mv.model_version_id not in _LOADED:
        _LOADED[mv.model_version_id] = load_model(REPO_ROOT / mv.artifact_path)
    return _LOADED[mv.model_version_id]


def preload_active_model(session: Session) -> ModelVersion | None:
    """Load the active learned model's files now, so the first cycle is not slowed down.

    Loading the boosters of the 3 horizons takes seconds (WORKFLOW 9.2 measured ~14 s, more
    than the 5-s cycle budget), so the cycle driver calls this at start-up and between polls.
    Returns the model, or None if no learned model is active or its files cannot be loaded;
    in that case the cycle itself falls back to B0, exactly as without a preload.
    """
    mv = repository.active_model_version(session)
    if mv is None or mv.model_family != "XGBOOST":
        return None
    try:
        _forecaster(mv)
    except Exception:  # missing / corrupt files: the cycle falls back to B0 and logs it
        log.warning("could not preload model %s", mv.model_version_id, exc_info=True)
        return None
    return mv


def _model_quantiles(
    session: Session,
    event: Event,
    zones: list[Zone],
    window_start: datetime,
    n: npt.NDArray[np.float64],
    fin: npt.NDArray[np.float64],
    fout: npt.NDArray[np.float64],
    speed: npt.NDArray[np.float64],
    mv: ModelVersion,
) -> dict[int, npt.NDArray[np.float64]]:
    """(Z, 3) occupancy quantiles per horizon from the shared FeatureBuilder + the model."""
    model = _forecaster(mv)
    venue = repository.get_venue(session, event.venue_id)
    assert venue is not None
    codes = tuple(z.code for z in zones)
    by_id = {z.zone_id: z.code for z in zones}
    info = venue_info_from_rows(
        [
            ZoneRow(
                z.code,
                float(z.planning_capacity),
                float(z.usable_area_m2),
                z.zone_type,
                z.is_entry,
                z.is_exit,
            )
            for z in zones
        ],
        [
            ConnectionRow(
                OUTSIDE if c.from_zone_id is None else by_id[c.from_zone_id],
                OUTSIDE if c.to_zone_id is None else by_id[c.to_zone_id],
                float(c.boundary_width_m),
                float(c.travel_time_s),
                c.bidirectional,
            )
            for c in repository.list_connections(session, event.venue_id)
        ],
        model.outflow_share(venue.name, codes),  # training-estimated; uniform if unknown venue
    )
    event_start = ensure_utc(event.start_time)
    idx = {c: k for k, c in enumerate(codes)}
    schedule = tuple(
        SchedItem(
            zone=None if code is None else idx[code],
            category=item.category,
            start_min=(ensure_utc(item.start_time) - event_start) / timedelta(minutes=1),
            end_min=(ensure_utc(item.end_time) - event_start) / timedelta(minutes=1),
            expected_attendance=None
            if item.expected_attendance is None
            else float(item.expected_attendance),
            attraction=float(item.attraction_weight),
        )
        for item, code in repository.list_schedule(session, event.event_id)  # published (DB)
    )
    hist = History(
        n=n,
        inflow=fin,
        outflow=fout,
        speed=speed,
        offset=int((window_start - event_start) / timedelta(minutes=1)),
        duration_min=(ensure_utc(event.end_time) - event_start) / timedelta(minutes=1),
        schedule=schedule,
    )
    out: dict[int, npt.NDArray[np.float64]] = {}
    for h in HORIZONS:
        rows = build_features(hist, info, model.feature_set, h)
        last = rows[rows["k"] == rows["k"].max()].sort_values("zone")
        q = model.predict(last, h, info.capacity)
        if not np.all(np.isfinite(q)):
            raise ValueError(f"non-finite forecast at h={h}")
        out[h] = q
    return out

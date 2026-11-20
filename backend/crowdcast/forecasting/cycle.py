"""One prediction cycle (doc 10 §12; WORKFLOW 4.2.1-4.2.3).

``run_cycle(session, event_id, issued_at)`` forecasts every zone at +5/+15/+30 min and writes
``predictions``. ``issued_at`` is a minute boundary in **event time**: the cycle sees only the
buckets that ended by then (bucket_start < issued_at), so replays at any speed-up and
back-fills produce the same predictions as a live run (no wall-clock time anywhere).

Model choice: there is no trained model yet, so every forecast is the B0 persistence fallback
(``is_fallback = true``, logged). When a learned model is active, a failure or a cold start
(< 15 min of history) still falls back to B0. Persistence has no spread, so p10 = p50 = p90
(no uncertainty is invented).

Data separation (CLAUDE.md §6): a synthetic event is forecast from SYNTHETIC observations,
any other event from REAL ones; MANUAL counts are ground truth, never model input here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy.orm import Session

from crowdcast.common.enums import DataOrigin
from crowdcast.common.time import ensure_utc, is_minute_aligned
from crowdcast.forecasting.baselines import HORIZONS, b0_persistence, forward_fill
from crowdcast.risk.interfaces import Thresholds, level, risk_score
from crowdcast.storage.interfaces import repository

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

    # (WINDOW_MIN, Z) occupancy, NaN where no observation; row -1 = the bucket that just ended
    n = np.full((WINDOW_MIN, len(zones)), np.nan)
    for o in obs:
        row = int((ensure_utc(o.bucket_start) - start) / timedelta(minutes=1))
        if o.occupancy is not None:
            n[row, col[o.zone_id]] = o.occupancy

    # A learned model would be tried here; none exists yet (Phase 5), so B0 is the fallback.
    active = repository.active_model_version(session)
    if active is not None:
        log.warning(
            "active model %s/%s not loadable yet; using B0 fallback", active.name, active.version
        )
    model_id = repository.baseline_model_version(session)

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
            p50 = float(b0_persistence(filled[:, k], h)[0])
            u = p50 / capacity
            rows.append(
                {
                    "event_id": event_id,
                    "zone_id": z.zone_id,
                    "issued_at": issued_at,
                    "horizon_min": h,
                    "target_time": issued_at + timedelta(minutes=h),
                    "p10": p50,
                    "p50": p50,
                    "p90": p50,
                    "predicted_level": level(u, thresholds),
                    "risk_score": risk_score(u, u, thresholds),
                    "model_version_id": model_id,
                    "is_fallback": True,
                }
            )
        result.fallback_zones.append(z.code)

    result.written = repository.upsert_predictions(session, rows)
    if result.fallback_zones:
        log.info(
            "event %s @ %s: B0 fallback for %d zones%s",
            event_id,
            issued_at.isoformat(),
            len(result.fallback_zones),
            f"; skipped {result.skipped_zones}" if result.skipped_zones else "",
        )
    return result

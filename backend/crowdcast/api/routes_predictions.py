"""Prediction read endpoints (doc 14 §3.11-3.12, amended in §6)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.common.enums import CongestionLevel
from crowdcast.forecasting.interfaces import HORIZONS, origin_for
from crowdcast.risk.interfaces import Thresholds, level
from crowdcast.storage.interfaces import Event, Prediction, repository

router = APIRouter(prefix="/api/predictions", tags=["predictions"])
ONE_MIN = timedelta(minutes=1)


class ModelRef(BaseModel):
    model_version_id: int
    name: str
    version: str


class Current(BaseModel):
    occupancy: int | None
    occupancy_ratio: float | None
    level: CongestionLevel | None


class Forecast(BaseModel):
    horizon_min: int
    target_time: datetime
    p10: float
    p50: float
    p90: float
    level: CongestionLevel
    risk_score: float | None
    is_fallback: bool


class ZoneForecasts(BaseModel):
    zone_id: int
    code: str
    current: Current
    forecasts: list[Forecast]


class LatestPredictions(BaseModel):
    event_id: int
    issued_at: datetime | None  # null if no cycle has run
    model: ModelRef | None
    zones: list[ZoneForecasts]


class TimelinePoint(BaseModel):
    issued_at: datetime
    horizon_min: int
    target_time: datetime
    p10: float
    p50: float
    p90: float
    is_fallback: bool
    actual: int | None  # observed occupancy at target_time, if known yet


class Timeline(BaseModel):
    event_id: int
    zone_id: int
    points: list[TimelinePoint]


def _event_or_404(session: SessionDep, event_id: int) -> Event:
    event = repository.get_event(session, event_id)
    if event is None:
        raise ApiError(404, "NOT_FOUND", f"event {event_id} not found")
    return event


def _forecast(p: Prediction) -> Forecast:
    return Forecast(
        horizon_min=p.horizon_min, target_time=p.target_time, p10=p.p10, p50=p.p50, p90=p.p90,
        level=p.predicted_level, risk_score=p.risk_score, is_fallback=p.is_fallback,
    )  # fmt: skip


@router.get("/{event_id}", response_model=LatestPredictions)
def latest_predictions(event_id: int, session: SessionDep) -> LatestPredictions:
    """The latest cycle (doc 14 §3.11); a learned model's rows win over fallback rows."""
    event = _event_or_404(session, event_id)
    issued = repository.latest_issued_at(session, event_id)
    if issued is None:
        return LatestPredictions(event_id=event_id, issued_at=None, model=None, zones=[])
    best: dict[tuple[int, int], Prediction] = {}
    for p in repository.predictions_at(session, event_id, [issued]):
        key = (p.zone_id, p.horizon_min)
        if key not in best or (best[key].is_fallback and not p.is_fallback):
            best[key] = p
    model_ids = {p.model_version_id for p in best.values()}
    model = repository.get_model_version(session, min(model_ids)) if model_ids else None
    observed = {
        o.zone_id: o.occupancy
        for o in repository.observation_window(
            session, event_id, origin_for(event.is_synthetic), issued - ONE_MIN, issued
        )
    }
    zones = []
    for z in repository.list_zones(session, event.venue_id):
        forecasts = [_forecast(best[(z.zone_id, h)]) for h in HORIZONS if (z.zone_id, h) in best]
        if not forecasts:
            continue
        occ = observed.get(z.zone_id)
        ratio = None if occ is None else occ / z.planning_capacity
        thr = Thresholds.from_overrides(
            z.threshold_elevated, z.threshold_high, z.threshold_critical
        )
        zones.append(
            ZoneForecasts(
                zone_id=z.zone_id,
                code=z.code,
                current=Current(
                    occupancy=occ,
                    occupancy_ratio=ratio,
                    level=None if ratio is None else level(ratio, thr),
                ),
                forecasts=forecasts,
            )
        )
    return LatestPredictions(
        event_id=event_id,
        issued_at=issued,
        model=None
        if model is None
        else ModelRef(
            model_version_id=model.model_version_id, name=model.name, version=model.version
        ),
        zones=zones,
    )


@router.get("/{event_id}/zones/{zone_id}", response_model=Timeline)
def zone_timeline(
    event_id: int,
    zone_id: int,
    session: SessionDep,
    horizon_min: Annotated[list[int] | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
) -> Timeline:
    """Predictions by target time joined with the actual occupancy (doc 14 §3.12)."""
    event = _event_or_404(session, event_id)
    if zone_id not in {z.zone_id for z in repository.list_zones(session, event.venue_id)}:
        raise ApiError(404, "NOT_FOUND", f"zone {zone_id} is not in this event's venue")
    horizons = horizon_min or list(HORIZONS)
    bad = sorted(set(horizons) - set(HORIZONS))
    if bad:
        raise ApiError(422, "VALIDATION_ERROR", f"horizon_min must be 5, 15 or 30 (got {bad})")
    start = from_ or event.start_time - timedelta(minutes=30)
    end = to or event.end_time + timedelta(minutes=60)
    preds = repository.zone_predictions(session, event_id, zone_id, horizons, start, end)
    actual = {
        o.bucket_start + ONE_MIN: o.occupancy
        for o in repository.history(
            session, event_id, origin_for(event.is_synthetic), start - ONE_MIN, end, [zone_id]
        )
    }
    return Timeline(
        event_id=event_id,
        zone_id=zone_id,
        points=[
            TimelinePoint(
                issued_at=p.issued_at,
                horizon_min=p.horizon_min,
                target_time=p.target_time,
                p10=p.p10,
                p50=p.p50,
                p90=p.p90,
                is_fallback=p.is_fallback,
                actual=actual.get(p.target_time),
            )
            for p in preds
        ],
    )

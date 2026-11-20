"""The single ingestion endpoint (AD-02; doc 14 §3.8, amended in §6).

The CV pipeline, CROWDSIM replay and annotation import all post here; nothing else writes
observations to the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.common.enums import CongestionLevel, DataOrigin, ObsQuality
from crowdcast.common.time import utc_now
from crowdcast.forecasting.interfaces import origin_for
from crowdcast.ingestion.interfaces import (
    BatchRejectedError,
    EventFacts,
    ObservationBatch,
    check_batch,
    check_rows,
)
from crowdcast.risk.interfaces import Thresholds, level
from crowdcast.storage.interfaces import Event, repository

router = APIRouter(prefix="/api/crowd", tags=["crowd"])


class RejectedOut(BaseModel):
    index: int  # position in the request's observations list
    zone_id: int
    bucket_start: datetime
    reason: str


class IngestResult(BaseModel):
    inserted: int
    updated: int
    rejected: list[RejectedOut]


@router.post("/observations", response_model=IngestResult)
def ingest_observations(batch: ObservationBatch, session: SessionDep) -> IngestResult:
    """Validate a batch, upsert the valid rows, report the rejected ones (HTTP 200)."""
    event = repository.get_event(session, batch.event_id)
    if event is None:
        raise ApiError(404, "NOT_FOUND", f"event {batch.event_id} not found")
    facts = EventFacts(event.status, event.is_synthetic, event.start_time, event.end_time)
    try:
        check_batch(batch, facts)
    except BatchRejectedError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc

    zone_ids = {z.zone_id for z in repository.list_zones(session, event.venue_id)}
    valid, rejected = check_rows(batch, facts, zone_ids, now=utc_now())
    inserted, updated = repository.upsert_observations(
        session, event.event_id, batch.data_origin, [row.model_dump() for _, row in valid]
    )
    return IngestResult(
        inserted=inserted,
        updated=updated,
        rejected=[RejectedOut(**r.__dict__) for r in rejected],
    )


# ---------------------------------------------------------------------- reads (4.4.1)
ONE_MIN = timedelta(minutes=1)
ORIGIN_PRECEDENCE = (DataOrigin.REAL, DataOrigin.MANUAL, DataOrigin.SYNTHETIC)  # doc 14 §3.10


class ZoneNow(BaseModel):
    zone_id: int
    code: str
    name: str
    occupancy: int | None
    capacity: int
    occupancy_ratio: float | None
    density_ppm2: float | None
    inflow: int | None
    outflow: int | None
    mean_speed_mps: float | None
    level: CongestionLevel | None
    quality: ObsQuality | None
    data_origin: DataOrigin
    staleness_s: int | None  # event time: as_of minus this zone's latest bucket end


class CurrentState(BaseModel):
    event_id: int
    as_of: datetime | None  # end of the newest bucket with data (event time)
    zones: list[ZoneNow]


class HistoryPoint(BaseModel):
    t: datetime  # bucket start
    occupancy: int | None
    inflow: int | None
    outflow: int | None


class Series(BaseModel):
    zone_id: int
    points: list[HistoryPoint]


class History(BaseModel):
    event_id: int
    origin: DataOrigin | None  # the single origin used (no mixing); null if no data
    resolution: str
    series: list[Series]


def _event_or_404(session: SessionDep, event_id: int) -> Event:
    event = repository.get_event(session, event_id)
    if event is None:
        raise ApiError(404, "NOT_FOUND", f"event {event_id} not found")
    return event


@router.get("/current/{event_id}", response_model=CurrentState)
def current_state(event_id: int, session: SessionDep) -> CurrentState:
    """Latest state of every zone (doc 14 §3.9). Uses the event's own data origin."""
    event = _event_or_404(session, event_id)
    origin = origin_for(event.is_synthetic)
    latest = {o.zone_id: o for o in repository.latest_observations(session, event_id, origin)}
    ends = [o.bucket_start + ONE_MIN for o in latest.values()]
    as_of = max(ends) if ends else None
    zones = []
    for z in repository.list_zones(session, event.venue_id):
        o = latest.get(z.zone_id)
        thr = Thresholds.from_overrides(
            z.threshold_elevated, z.threshold_high, z.threshold_critical
        )
        occ = None if o is None else o.occupancy
        ratio = None if occ is None else occ / z.planning_capacity
        zones.append(
            ZoneNow(
                zone_id=z.zone_id, code=z.code, name=z.name, occupancy=occ,
                capacity=z.planning_capacity, occupancy_ratio=ratio,
                density_ppm2=None if occ is None else occ / float(z.usable_area_m2),
                inflow=None if o is None else o.inflow,
                outflow=None if o is None else o.outflow,
                mean_speed_mps=None if o is None else o.mean_speed_mps,
                level=None if ratio is None else level(ratio, thr),
                quality=None if o is None else o.quality,
                data_origin=origin,
                staleness_s=None
                if o is None or as_of is None
                else int((as_of - (o.bucket_start + ONE_MIN)).total_seconds()),
            )
        )  # fmt: skip
    return CurrentState(event_id=event_id, as_of=as_of, zones=zones)


@router.get("/history/{event_id}", response_model=History)
def crowd_history(
    event_id: int,
    session: SessionDep,
    zone_id: Annotated[list[int] | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    origin: DataOrigin | None = None,
    resolution: Literal["1m", "5m"] = "1m",
) -> History:
    """Time series per zone (doc 14 §3.10). One origin only; 5m = last occupancy, summed flows."""
    event = _event_or_404(session, event_id)
    start = from_ or event.start_time - timedelta(minutes=30)
    end = to or event.end_time + timedelta(minutes=30)
    if start.tzinfo is None or end.tzinfo is None:
        raise ApiError(422, "VALIDATION_ERROR", "from/to need a time zone (e.g. Z)")
    if not start < end:
        raise ApiError(422, "VALIDATION_ERROR", "from must be before to")
    if end - start > timedelta(hours=24):
        raise ApiError(422, "VALIDATION_ERROR", "range may be at most 24 h")
    if origin is None:
        have = repository.origins_with_data(session, event_id, start, end)
        origin = next((o for o in ORIGIN_PRECEDENCE if o in have), None)
    rows = (
        [] if origin is None else repository.history(session, event_id, origin, start, end, zone_id)
    )
    by_zone: dict[int, list[HistoryPoint]] = {}
    for o in rows:
        by_zone.setdefault(o.zone_id, []).append(
            HistoryPoint(
                t=o.bucket_start, occupancy=o.occupancy, inflow=o.inflow, outflow=o.outflow
            )
        )
    if resolution == "5m":
        by_zone = {z: _five_minute(points) for z, points in by_zone.items()}
    return History(
        event_id=event_id,
        origin=origin,
        resolution=resolution,
        series=[Series(zone_id=z, points=p) for z, p in sorted(by_zone.items())],
    )


def _five_minute(points: list[HistoryPoint]) -> list[HistoryPoint]:
    bins: dict[datetime, list[HistoryPoint]] = {}
    for p in points:
        key = p.t - timedelta(minutes=p.t.minute % 5)
        bins.setdefault(key, []).append(p)
    out = []
    for key, ps in sorted(bins.items()):
        flows_in = [p.inflow for p in ps if p.inflow is not None]
        flows_out = [p.outflow for p in ps if p.outflow is not None]
        out.append(
            HistoryPoint(
                t=key,
                occupancy=ps[-1].occupancy,  # end-of-bucket semantics: the last minute's value
                inflow=sum(flows_in) if flows_in else None,
                outflow=sum(flows_out) if flows_out else None,
            )
        )
    return out

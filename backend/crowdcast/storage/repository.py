"""Read queries and small updates used by the API (WORKFLOW 2.3.3).

Keeps SQL in the storage module; the API maps the returned rows to its response schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import ReturningInsert

from crowdcast.common.enums import DataOrigin, EventStatus
from crowdcast.storage.models import (
    AuditLog,
    CameraSource,
    CrowdObservation,
    Event,
    EventScheduleItem,
    ModelVersion,
    Venue,
    Zone,
    ZoneConnection,
)
from crowdcast.venue_graph.interfaces import OUTSIDE, Connection, VenueGraph

# Allowed status transitions (doc 14 §3.4).
TRANSITIONS: dict[EventStatus, EventStatus] = {
    EventStatus.PLANNED: EventStatus.LIVE,
    EventStatus.LIVE: EventStatus.ENDED,
}


@dataclass(frozen=True)
class EventCounts:
    zone_count: int
    camera_count: int
    schedule_item_count: int


def get_venue(session: Session, venue_id: int) -> Venue | None:
    return session.get(Venue, venue_id)


def list_zones(session: Session, venue_id: int) -> list[Zone]:
    return list(
        session.scalars(select(Zone).where(Zone.venue_id == venue_id).order_by(Zone.zone_id))
    )


def list_connections(session: Session, venue_id: int) -> list[ZoneConnection]:
    stmt = (
        select(ZoneConnection)
        .where(ZoneConnection.venue_id == venue_id)
        .order_by(ZoneConnection.connection_id)
    )
    return list(session.scalars(stmt))


def venue_graph(session: Session, venue_id: int) -> VenueGraph:
    """Build the venue graph from the stored zones and connections (NULL zone = OUTSIDE)."""
    zones = list_zones(session, venue_id)
    code = {z.zone_id: z.code for z in zones}
    conns = [
        Connection(
            from_code=OUTSIDE if c.from_zone_id is None else code[c.from_zone_id],
            to_code=OUTSIDE if c.to_zone_id is None else code[c.to_zone_id],
            width_m=float(c.boundary_width_m),
            travel_time_s=c.travel_time_s,
            bidirectional=c.bidirectional,
        )
        for c in list_connections(session, venue_id)
    ]
    return VenueGraph.from_connections([z.code for z in zones], conns)


def list_events(session: Session, *, limit: int, before_id: int | None = None) -> list[Event]:
    """Newest first (by id); ``before_id`` is the keyset cursor from the previous page."""
    stmt = select(Event).order_by(Event.event_id.desc()).limit(limit)
    if before_id is not None:
        stmt = stmt.where(Event.event_id < before_id)
    return list(session.scalars(stmt))


def get_event(session: Session, event_id: int) -> Event | None:
    return session.get(Event, event_id)


def event_counts(session: Session, event: Event) -> EventCounts:
    def count(stmt: object) -> int:
        return int(session.scalar(stmt) or 0)  # type: ignore[call-overload]

    return EventCounts(
        zone_count=count(
            select(func.count()).select_from(Zone).where(Zone.venue_id == event.venue_id)
        ),
        camera_count=count(
            select(func.count())
            .select_from(CameraSource)
            .where(CameraSource.venue_id == event.venue_id)
        ),
        schedule_item_count=count(
            select(func.count())
            .select_from(EventScheduleItem)
            .where(EventScheduleItem.event_id == event.event_id)
        ),
    )


def get_model_version(session: Session, model_version_id: int | None) -> ModelVersion | None:
    return None if model_version_id is None else session.get(ModelVersion, model_version_id)


def list_schedule(session: Session, event_id: int) -> list[tuple[EventScheduleItem, str | None]]:
    """Schedule items in start order, each with its zone code (None = venue-wide)."""
    stmt = (
        select(EventScheduleItem, Zone.code)
        .outerjoin(Zone, Zone.zone_id == EventScheduleItem.zone_id)
        .where(EventScheduleItem.event_id == event_id)
        .order_by(EventScheduleItem.start_time, EventScheduleItem.item_id)
    )
    return [(item, code) for item, code in session.execute(stmt)]


def set_event_status(session: Session, event: Event, new_status: EventStatus) -> None:
    """Apply an allowed transition and audit it; the caller checks ``TRANSITIONS`` first."""
    old = event.status
    event.status = new_status
    session.add(
        AuditLog(
            actor="USER",
            action="EVENT_STATUS",
            entity="event",
            entity_id=event.event_id,
            details={"from": old.value, "to": new_status.value},
        )
    )
    session.flush()


OBSERVATION_FIELDS = (
    "zone_id",
    "bucket_start",
    "occupancy",
    "occupancy_raw",
    "inflow",
    "outflow",
    "mean_speed_mps",
    "quality",
    "method",
)


def upsert_observations(
    session: Session, event_id: int, origin: DataOrigin, rows: list[dict[str, Any]]
) -> tuple[int, int]:
    """Insert or update zone-minutes on the key (event, zone, bucket, origin); validated rows only.

    Returns (inserted, updated). A later batch for the same key replaces the stored values, so a
    replay can be re-run safely. Uses PostgreSQL's ``xmax = 0`` to tell inserts from updates.
    """
    if not rows:
        return 0, 0
    values = [
        {"event_id": event_id, "data_origin": origin, **{f: r[f] for f in OBSERVATION_FIELDS}}
        for r in rows
    ]
    ins = insert(CrowdObservation).values(values)
    keep = ("zone_id", "bucket_start")  # part of the conflict key
    upsert = ins.on_conflict_do_update(
        index_elements=["event_id", "zone_id", "bucket_start", "data_origin"],
        set_={
            **{f: ins.excluded[f] for f in OBSERVATION_FIELDS if f not in keep},
            "ingested_at": func.now(),
        },
    )
    stmt: ReturningInsert[tuple[bool]] = upsert.returning(literal_column("(xmax = 0)"))
    flags = list(session.scalars(stmt))
    inserted = sum(1 for f in flags if f)
    return inserted, len(flags) - inserted

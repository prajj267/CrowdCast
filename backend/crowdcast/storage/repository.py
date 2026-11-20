"""Read queries and small updates used by the API (WORKFLOW 2.3.3).

Keeps SQL in the storage module; the API maps the returned rows to its response schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import ReturningInsert

from crowdcast.common.enums import AlertStatus, DataOrigin, EventStatus
from crowdcast.storage.models import (
    AuditLog,
    CameraSource,
    CongestionAlert,
    CrowdObservation,
    Event,
    EventScheduleItem,
    ModelVersion,
    Prediction,
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


# ---------------------------------------------------------------------- prediction cycle
BASELINE_MODEL = {
    "name": "B0_persistence",
    "version": "1",
    "model_family": "PERSISTENCE",
    "artifact_path": "builtin:crowdcast.forecasting.baselines.b0_persistence",
}


def baseline_model_version(session: Session) -> int:
    """Id of the built-in persistence model (created on first use; never marked active)."""
    existing = session.scalar(
        select(ModelVersion.model_version_id).where(
            ModelVersion.name == BASELINE_MODEL["name"],
            ModelVersion.version == BASELINE_MODEL["version"],
        )
    )
    if existing is not None:
        return existing
    row = ModelVersion(**BASELINE_MODEL, feature_set=None, is_active=False)
    session.add(row)
    session.flush()
    return row.model_version_id


def active_model_version(session: Session) -> ModelVersion | None:
    return session.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))


def observation_window(
    session: Session, event_id: int, origin: DataOrigin, start: datetime, end: datetime
) -> list[CrowdObservation]:
    """Observations of one origin with start <= bucket_start < end, in time order."""
    stmt = (
        select(CrowdObservation)
        .where(
            CrowdObservation.event_id == event_id,
            CrowdObservation.data_origin == origin,
            CrowdObservation.bucket_start >= start,
            CrowdObservation.bucket_start < end,
        )
        .order_by(CrowdObservation.bucket_start)
    )
    return list(session.scalars(stmt))


def observation_bucket_range(
    session: Session, event_id: int, origin: DataOrigin
) -> tuple[datetime | None, datetime | None]:
    row = session.execute(
        select(
            func.min(CrowdObservation.bucket_start), func.max(CrowdObservation.bucket_start)
        ).where(CrowdObservation.event_id == event_id, CrowdObservation.data_origin == origin)
    ).one()
    return row[0], row[1]


PREDICTION_FIELDS = (
    "target_time", "p10", "p50", "p90", "predicted_level", "risk_score", "is_fallback",
)  # fmt: skip


def upsert_predictions(session: Session, rows: list[dict[str, Any]]) -> int:
    """Insert or update on (event, zone, issued_at, horizon, model) - a cycle can be re-run."""
    if not rows:
        return 0
    ins = insert(Prediction).values(rows)
    stmt = ins.on_conflict_do_update(
        index_elements=["event_id", "zone_id", "issued_at", "horizon_min", "model_version_id"],
        set_={f: ins.excluded[f] for f in PREDICTION_FIELDS},
    )
    session.execute(stmt)
    return len(rows)


# ---------------------------------------------------------------------- alerts (M7)
def predictions_at(session: Session, event_id: int, issued_ats: list[datetime]) -> list[Prediction]:
    stmt = select(Prediction).where(
        Prediction.event_id == event_id, Prediction.issued_at.in_(issued_ats)
    )
    return list(session.scalars(stmt))


def unresolved_alerts(session: Session, event_id: int) -> list[CongestionAlert]:
    stmt = select(CongestionAlert).where(
        CongestionAlert.event_id == event_id, CongestionAlert.status != AlertStatus.RESOLVED
    )
    return list(session.scalars(stmt))


def add_audit(
    session: Session,
    action: str,
    entity: str,
    entity_id: int,
    details: dict[str, Any],
    actor: str = "SYSTEM",
) -> None:
    session.add(
        AuditLog(actor=actor, action=action, entity=entity, entity_id=entity_id, details=details)
    )


# ---------------------------------------------------------------------- dashboard reads (4.4)
def latest_observations(
    session: Session, event_id: int, origin: DataOrigin
) -> list[CrowdObservation]:
    """The newest observation of each zone for one origin."""
    newest = (
        select(CrowdObservation.zone_id, func.max(CrowdObservation.bucket_start).label("b"))
        .where(CrowdObservation.event_id == event_id, CrowdObservation.data_origin == origin)
        .group_by(CrowdObservation.zone_id)
        .subquery()
    )
    stmt = (
        select(CrowdObservation)
        .join(
            newest,
            (CrowdObservation.zone_id == newest.c.zone_id)
            & (CrowdObservation.bucket_start == newest.c.b),
        )
        .where(CrowdObservation.event_id == event_id, CrowdObservation.data_origin == origin)
    )
    return list(session.scalars(stmt))


def origins_with_data(
    session: Session, event_id: int, start: datetime, end: datetime
) -> set[DataOrigin]:
    stmt = (
        select(CrowdObservation.data_origin)
        .where(
            CrowdObservation.event_id == event_id,
            CrowdObservation.bucket_start >= start,
            CrowdObservation.bucket_start < end,
        )
        .distinct()
    )
    return set(session.scalars(stmt))


def history(
    session: Session,
    event_id: int,
    origin: DataOrigin,
    start: datetime,
    end: datetime,
    zone_ids: list[int] | None,
) -> list[CrowdObservation]:
    stmt = (
        select(CrowdObservation)
        .where(
            CrowdObservation.event_id == event_id,
            CrowdObservation.data_origin == origin,
            CrowdObservation.bucket_start >= start,
            CrowdObservation.bucket_start < end,
        )
        .order_by(CrowdObservation.zone_id, CrowdObservation.bucket_start)
    )
    if zone_ids:
        stmt = stmt.where(CrowdObservation.zone_id.in_(zone_ids))
    return list(session.scalars(stmt))


def latest_issued_at(session: Session, event_id: int) -> datetime | None:
    latest: datetime | None = session.scalar(
        select(func.max(Prediction.issued_at)).where(Prediction.event_id == event_id)
    )
    return latest


def zone_predictions(
    session: Session,
    event_id: int,
    zone_id: int,
    horizons: list[int],
    start: datetime,
    end: datetime,
) -> list[Prediction]:
    """Predictions whose target_time lies in [start, end], oldest target first."""
    stmt = (
        select(Prediction)
        .where(
            Prediction.event_id == event_id,
            Prediction.zone_id == zone_id,
            Prediction.horizon_min.in_(horizons),
            Prediction.target_time >= start,
            Prediction.target_time <= end,
        )
        .order_by(Prediction.target_time, Prediction.horizon_min)
    )
    return list(session.scalars(stmt))


def list_alerts(
    session: Session,
    event_id: int,
    *,
    statuses: list[AlertStatus] | None,
    level: str | None,
    zone_id: int | None,
    limit: int,
    before_id: int | None,
) -> list[CongestionAlert]:
    stmt = (
        select(CongestionAlert)
        .where(CongestionAlert.event_id == event_id)
        .order_by(CongestionAlert.alert_id.desc())
        .limit(limit)
    )
    if statuses:
        stmt = stmt.where(CongestionAlert.status.in_(statuses))
    if level is not None:
        stmt = stmt.where(CongestionAlert.level == level)
    if zone_id is not None:
        stmt = stmt.where(CongestionAlert.zone_id == zone_id)
    if before_id is not None:
        stmt = stmt.where(CongestionAlert.alert_id < before_id)
    return list(session.scalars(stmt))


def get_alert(session: Session, alert_id: int) -> CongestionAlert | None:
    return session.get(CongestionAlert, alert_id)

"""Load venue and event YAML configuration into PostgreSQL (WORKFLOW 2.3.1).

Everything is validated before anything is written: the YAML formats (doc 12 §6), the graph
rules (doc 11 §9) and the schedule's zone codes. Writes happen in the caller's transaction, so
a failure leaves the database unchanged. Existing rows are never overwritten: loading a venue or
event that already exists is an error.

This is configuration, not crowd data: observations still enter only through
``POST /api/crowd/observations`` (AD-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from crowdcast.storage.models import (
    AuditLog,
    Event,
    EventScheduleItem,
    Venue,
    Zone,
    ZoneConnection,
)
from crowdcast.venue_graph.interfaces import (
    OUTSIDE,
    EventConfig,
    GraphIssue,
    VenueConfig,
    VenueGraph,
)


class AlreadyLoadedError(ValueError):
    """The venue or event exists already; nothing was written."""


@dataclass(frozen=True)
class VenueLoadResult:
    venue_id: int
    zone_ids: dict[str, int]
    connection_count: int
    warnings: list[GraphIssue]


@dataclass(frozen=True)
class EventLoadResult:
    event_id: int
    schedule_item_count: int


def _dec(value: float) -> Decimal:
    # via str() so 1.5 is stored as 1.5, not 1.4999999999999999...
    return Decimal(str(value))


def load_venue(session: Session, cfg: VenueConfig) -> VenueLoadResult:
    """Insert a venue with its zones and connections. Raises if the graph is invalid."""
    warnings = VenueGraph.from_config(cfg).require_valid()
    existing = session.scalar(select(Venue.venue_id).where(Venue.name == cfg.venue.name))
    if existing is not None:
        raise AlreadyLoadedError(f"venue {cfg.venue.name!r} already exists (venue_id={existing})")

    v = cfg.venue
    venue = Venue(
        name=v.name,
        address=v.address,
        floor_plan_path=v.floor_plan_path,
        plan_width=v.plan_width,
        plan_height=v.plan_height,
        rho_plan=None if v.rho_plan is None else _dec(v.rho_plan),
    )
    session.add(venue)
    session.flush()  # assigns venue_id

    zone_ids: dict[str, int] = {}
    for z in cfg.zones:
        t = z.thresholds
        zone = Zone(
            venue_id=venue.venue_id,
            code=z.code,
            name=z.name,
            zone_type=z.type,
            usable_area_m2=_dec(z.area_m2),
            planning_capacity=cfg.capacity_of(z.code),
            polygon=[[x, y] for x, y in z.polygon],
            is_entry=cfg.is_entry(z.code),
            is_exit=cfg.is_exit(z.code),
            # Only explicit overrides are stored; NULL means "use the default" (doc 13).
            threshold_elevated=None if t.elevated is None else _dec(t.elevated),
            threshold_high=None if t.high is None else _dec(t.high),
            threshold_critical=None if t.critical is None else _dec(t.critical),
        )
        session.add(zone)
        session.flush()
        zone_ids[z.code] = zone.zone_id

    for c in cfg.connections:
        session.add(
            ZoneConnection(
                venue_id=venue.venue_id,
                from_zone_id=None if c.from_ == OUTSIDE else zone_ids[c.from_],
                to_zone_id=None if c.to == OUTSIDE else zone_ids[c.to],
                boundary_width_m=_dec(c.width_m),
                travel_time_s=c.travel_time_s,
                bidirectional=c.bidirectional,
            )
        )
    session.add(
        AuditLog(
            actor="SYSTEM",
            action="VENUE_LOAD",
            entity="venue",
            entity_id=venue.venue_id,
            details={
                "name": v.name,
                "zones": len(cfg.zones),
                "connections": len(cfg.connections),
                "illustrative": cfg.illustrative,
            },
        )
    )
    session.flush()
    return VenueLoadResult(venue.venue_id, zone_ids, len(cfg.connections), warnings)


def load_event(session: Session, cfg: EventConfig, venue_cfg: VenueConfig) -> EventLoadResult:
    """Insert an event and its published schedule at an already-loaded venue."""
    cfg.check_against_venue(venue_cfg)
    venue_id = session.scalar(select(Venue.venue_id).where(Venue.name == venue_cfg.venue.name))
    if venue_id is None:
        raise LookupError(f"venue {venue_cfg.venue.name!r} is not loaded; load it first")
    e = cfg.event
    duplicate = session.scalar(
        select(Event.event_id).where(
            Event.venue_id == venue_id, Event.name == e.name, Event.start_time == e.start_time
        )
    )
    if duplicate is not None:
        raise AlreadyLoadedError(f"event {e.name!r} already exists (event_id={duplicate})")

    rows = session.execute(select(Zone.code, Zone.zone_id).where(Zone.venue_id == venue_id))
    zone_ids: dict[str, int] = {code: zone_id for code, zone_id in rows}
    event = Event(
        venue_id=venue_id,
        name=e.name,
        start_time=e.start_time,
        end_time=e.end_time,
        expected_attendance=e.expected_attendance,
        is_synthetic=e.is_synthetic,
    )
    session.add(event)
    session.flush()
    for item in cfg.schedule:
        session.add(
            EventScheduleItem(
                event_id=event.event_id,
                zone_id=None if item.zone is None else zone_ids[item.zone],
                title=item.title,
                category=item.category,
                start_time=item.start,
                end_time=item.end,
                expected_attendance=item.expected_attendance,
                attraction_weight=_dec(item.attraction_weight),
            )
        )
    session.add(
        AuditLog(
            actor="SYSTEM",
            action="EVENT_LOAD",
            entity="event",
            entity_id=event.event_id,
            details={
                "name": e.name,
                "schedule_items": len(cfg.schedule),
                "illustrative": cfg.illustrative,
            },
        )
    )
    session.flush()
    return EventLoadResult(event.event_id, len(cfg.schedule))

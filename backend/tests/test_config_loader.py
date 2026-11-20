"""Tests for loading venue/event YAML into PostgreSQL (task 2.3.1). Need the db container."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crowdcast.storage.interfaces import AlreadyLoadedError, load_event, load_venue
from crowdcast.storage.models import AuditLog, Event, EventScheduleItem, Zone, ZoneConnection
from crowdcast.venue_graph.interfaces import (
    InvalidVenueGraphError,
    VenueConfig,
    load_event_config,
    load_venue_config,
)

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
V1 = CONFIGS / "venues" / "v1.yaml"
EVENT = CONFIGS / "events" / "v1_spring_fest_day1.yaml"


def _v1() -> VenueConfig:
    """V1 under a unique name, so tests never collide with venues loaded in the dev DB."""
    cfg = load_venue_config(V1)
    name = f"Test V1 {uuid.uuid4().hex[:8]}"
    return cfg.model_copy(update={"venue": cfg.venue.model_copy(update={"name": name})})


def test_load_v1_venue(db_session: Session) -> None:
    r = load_venue(db_session, _v1())
    assert len(r.zone_ids) == 8  # Phase 2 exit criterion
    assert r.connection_count == 10
    zones = {z.code: z for z in db_session.scalars(select(Zone).where(Zone.venue_id == r.venue_id))}
    assert zones["MS"].planning_capacity == 3000
    assert zones["MS"].usable_area_m2 == Decimal("2000.00")
    assert (zones["G1"].is_entry, zones["G1"].is_exit) == (True, True)
    assert (zones["G2"].is_entry, zones["G2"].is_exit) == (False, True)
    assert zones["WC"].threshold_high is None  # defaults are not copied into the row

    conns = db_session.scalars(
        select(ZoneConnection).where(ZoneConnection.venue_id == r.venue_id)
    ).all()
    gate_out = [c for c in conns if c.to_zone_id is None]  # NULL = OUTSIDE
    assert len(gate_out) == 1 and gate_out[0].from_zone_id == zones["G2"].zone_id
    assert gate_out[0].bidirectional is False
    audit = db_session.scalar(select(AuditLog).where(AuditLog.entity_id == r.venue_id))
    assert audit is not None and audit.action == "VENUE_LOAD"
    assert audit.details is not None and audit.details["illustrative"] is True


def test_loading_same_venue_twice_is_refused(db_session: Session) -> None:
    cfg = _v1()
    load_venue(db_session, cfg)
    with pytest.raises(AlreadyLoadedError, match="already exists"):
        load_venue(db_session, cfg)


def test_invalid_graph_writes_nothing(db_session: Session) -> None:
    data = _v1().model_dump(by_alias=True)
    data["venue"]["name"] = "Broken venue"
    data["connections"] = [c for c in data["connections"] if "WC" not in (c["from"], c["to"])]
    before = db_session.scalar(select(func.count()).select_from(Zone))
    with pytest.raises(InvalidVenueGraphError, match="ISOLATED WC"):
        load_venue(db_session, VenueConfig.model_validate(data))
    assert db_session.scalar(select(func.count()).select_from(Zone)) == before


def test_load_event_with_schedule(db_session: Session) -> None:
    venue_cfg = _v1()
    v = load_venue(db_session, venue_cfg)
    r = load_event(db_session, load_event_config(EVENT), venue_cfg)
    assert r.schedule_item_count == 9
    event = db_session.get(Event, r.event_id)
    assert event is not None
    assert event.start_time == datetime(2027, 3, 12, 10, 30, tzinfo=UTC)
    assert event.status.value == "PLANNED" and event.is_synthetic is True
    items = db_session.scalars(
        select(EventScheduleItem).where(EventScheduleItem.event_id == r.event_id)
    ).all()
    headline = next(i for i in items if i.title == "Headline band")
    assert headline.zone_id == v.zone_ids["MS"]
    assert headline.attraction_weight == Decimal("0.95")
    assert sum(i.zone_id is None for i in items) == 2  # venue-wide: gates open, exit wave

    with pytest.raises(AlreadyLoadedError):
        load_event(db_session, load_event_config(EVENT), venue_cfg)


def test_event_needs_loaded_venue(db_session: Session) -> None:
    venue_cfg = load_venue_config(V1).model_copy(
        update={"venue": load_venue_config(V1).venue.model_copy(update={"name": "Not loaded"})}
    )
    with pytest.raises(LookupError, match="not loaded"):
        load_event(db_session, load_event_config(EVENT), venue_cfg)

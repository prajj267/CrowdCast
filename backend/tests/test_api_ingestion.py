"""Tests for POST /api/crowd/observations (tasks 3.1.1-3.1.2; doc 14 §3.8 and §6)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from crowdcast.api.app import create_app
from crowdcast.api.deps import get_session
from crowdcast.common.enums import EventStatus
from crowdcast.common.time import floor_to_minute, utc_now
from crowdcast.storage.interfaces import Event, load_event, load_venue
from crowdcast.storage.models import CrowdObservation
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
URL = "/api/crowd/observations"


@dataclass
class World:
    client: TestClient
    session: Session
    event: Event
    zone_ids: dict[str, int]
    t0: datetime  # a minute inside the event

    def post(self, origin: str, rows: list[dict[str, Any]]) -> Any:
        body = {"event_id": self.event.event_id, "data_origin": origin, "observations": rows}
        return self.client.post(URL, json=body)

    def row(self, zone: str = "MS", minutes: int = 0, **kw: Any) -> dict[str, Any]:
        base = {
            "zone_id": self.zone_ids[zone],
            "bucket_start": (self.t0 + timedelta(minutes=minutes)).isoformat(),
            "occupancy": 100,
            "inflow": 10,
            "outflow": 5,
            "quality": "OK",
            "method": "SIM_CLEAN",
        }
        return {**base, **kw}

    def stored(self) -> list[CrowdObservation]:
        stmt = select(CrowdObservation).where(CrowdObservation.event_id == self.event.event_id)
        return list(self.session.scalars(stmt))


@pytest.fixture
def world(db_session: Session) -> Iterator[World]:
    cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    name = f"Ingest test {uuid.uuid4().hex[:8]}"
    cfg = cfg.model_copy(update={"venue": cfg.venue.model_copy(update={"name": name})})
    v = load_venue(db_session, cfg)
    e = load_event(
        db_session, load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml"), cfg
    )
    event = db_session.get(Event, e.event_id)
    assert event is not None
    # Move the event around "now" so REAL rows pass the future check; start LIVE + synthetic.
    now = floor_to_minute(utc_now())
    event.start_time, event.end_time = now - timedelta(hours=2), now + timedelta(hours=2)
    event.status = EventStatus.LIVE
    db_session.flush()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield World(client, db_session, event, v.zone_ids, now - timedelta(minutes=30))


# ------------------------------------------------------------------ accepted batches
def test_valid_batch_is_inserted(world: World) -> None:
    r = world.post("SYNTHETIC", [world.row("MS"), world.row("C1"), world.row("MS", 1)])
    assert r.status_code == 200
    assert r.json() == {"inserted": 3, "updated": 0, "rejected": []}
    stored = world.stored()
    assert len(stored) == 3
    assert {o.data_origin.value for o in stored} == {"SYNTHETIC"}


def test_same_key_again_is_an_update(world: World) -> None:
    world.post("SYNTHETIC", [world.row("MS", occupancy=100)])
    r = world.post("SYNTHETIC", [world.row("MS", occupancy=250), world.row("C1")])
    assert r.json() == {"inserted": 1, "updated": 1, "rejected": []}
    ms = [o for o in world.stored() if o.zone_id == world.zone_ids["MS"]]
    assert len(ms) == 1 and ms[0].occupancy == 250


def test_missing_quality_allows_null_occupancy(world: World) -> None:
    r = world.post("SYNTHETIC", [world.row(occupancy=None, quality="MISSING")])
    assert r.json()["inserted"] == 1


# ------------------------------------------------------------------ partial rejection
def test_partial_rejection_keeps_valid_rows(world: World) -> None:
    rows = [
        world.row("MS"),  # 0 ok
        world.row("MS", 1, bucket_start=(world.t0 + timedelta(seconds=30)).isoformat()),  # 1
        world.row("MS", 2, zone_id=999_999_999),  # 2 wrong zone
        world.row("C1", inflow=-1),  # 3 negative
        world.row("C2", occupancy=None),  # 4 null without MISSING
        world.row("MS"),  # 5 duplicate of row 0
        world.row("EX", bucket_start=(world.event.end_time + timedelta(hours=1)).isoformat()),
    ]
    r = world.post("SYNTHETIC", rows)
    assert r.status_code == 200
    body = r.json()
    assert (body["inserted"], body["updated"]) == (1, 0)
    reasons = {x["index"]: x["reason"] for x in body["rejected"]}
    assert reasons == {
        1: "bucket_start is not minute-aligned",
        2: "zone does not belong to the event's venue",
        3: "inflow must be >= 0",
        4: "occupancy may be null only when quality = MISSING",
        5: "duplicate of row 0 (same zone and bucket)",
        6: "bucket_start outside the event window +/- 30 min",
    }
    assert len(world.stored()) == 1


def test_zone_of_another_venue_is_rejected(world: World, db_session: Session) -> None:
    other = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    other = other.model_copy(
        update={"venue": other.venue.model_copy(update={"name": f"Other {uuid.uuid4().hex[:6]}"})}
    )
    foreign_zone = load_venue(db_session, other).zone_ids["MS"]
    r = world.post("SYNTHETIC", [world.row(zone_id=foreign_zone)])
    assert r.json()["rejected"][0]["reason"] == "zone does not belong to the event's venue"


def test_real_rows_from_the_future_are_rejected(world: World) -> None:
    world.event.is_synthetic = False
    world.session.flush()
    future = floor_to_minute(utc_now()) + timedelta(minutes=10)
    r = world.post(
        "REAL",
        [
            world.row(method="DETECTION"),
            world.row("C1", bucket_start=future.isoformat(), method="DETECTION"),
        ],
    )
    body = r.json()
    assert body["inserted"] == 1
    assert body["rejected"][0]["reason"] == "bucket_start more than 2 min in the future"


# ------------------------------------------------------------------ whole-batch errors
def test_synthetic_into_real_event_is_refused(world: World) -> None:
    world.event.is_synthetic = False
    world.session.flush()
    r = world.post("SYNTHETIC", [world.row()])
    assert r.status_code == 422
    assert "is_synthetic" in r.json()["error"]["message"]
    assert world.stored() == []


def test_real_data_needs_a_live_event(world: World) -> None:
    world.event.is_synthetic = False
    world.event.status = EventStatus.ENDED
    world.session.flush()
    assert world.post("REAL", [world.row(method="DETECTION")]).status_code == 409
    # ...but annotated back-fill into an ended event is allowed
    r = world.post("MANUAL", [world.row(method="MANUAL")])
    assert r.status_code == 200 and r.json()["inserted"] == 1


def test_unknown_event_is_404(world: World) -> None:
    body = {"event_id": 999_999_999, "data_origin": "SYNTHETIC", "observations": [world.row()]}
    assert world.client.post(URL, json=body).status_code == 404


@pytest.mark.parametrize("count", [0, 1001])
def test_batch_size_limits(world: World, count: int) -> None:
    rows = [world.row(minutes=i % 60) for i in range(count)]
    r = world.post("SYNTHETIC", rows)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_structural_error_rejects_whole_batch(world: World) -> None:
    r = world.post("SYNTHETIC", [world.row(), world.row("C1", quality="GREAT")])
    assert r.status_code == 422
    assert world.stored() == []

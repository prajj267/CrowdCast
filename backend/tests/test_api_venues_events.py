"""API tests for venue/zone/event read endpoints and status transitions (task 2.3.4)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from crowdcast.api.app import create_app
from crowdcast.api.deps import get_session
from crowdcast.storage.interfaces import ZoneConnection, load_event, load_venue
from crowdcast.storage.models import AuditLog
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"


@dataclass
class World:
    client: TestClient
    session: Session
    venue_id: int
    event_id: int
    zone_ids: dict[str, int]


@pytest.fixture
def world(db_session: Session) -> Iterator[World]:
    cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    name = f"API test {uuid.uuid4().hex[:8]}"
    cfg = cfg.model_copy(update={"venue": cfg.venue.model_copy(update={"name": name})})
    v = load_venue(db_session, cfg)
    e = load_event(
        db_session, load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml"), cfg
    )
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session  # rolled back after the test
    with TestClient(app) as client:
        yield World(client, db_session, v.venue_id, e.event_id, v.zone_ids)


# ------------------------------------------------------------------ venues and zones
def test_get_venue(world: World) -> None:
    r = world.client.get(f"/api/venues/{world.venue_id}")
    assert r.status_code == 200
    assert r.json()["rho_plan"] == 1.5 and r.json()["plan_width"] == 1200


def test_zones_match_doc_14_shape(world: World) -> None:
    """Phase 2 exit criterion: the 8 V1 zones come back through the API."""
    r = world.client.get(f"/api/venues/{world.venue_id}/zones")
    assert r.status_code == 200
    zones = {z["code"]: z for z in r.json()["zones"]}
    assert len(zones) == 8
    ms = zones["MS"]
    assert ms["usable_area_m2"] == 2000.0 and ms["planning_capacity"] == 3000
    assert ms["polygon"] == [[600, 100], [1100, 100], [1100, 450], [600, 450]]
    assert ms["thresholds"] == {"elevated": 0.6, "high": 0.8, "critical": 0.95, "source": "DEFAULT"}
    ids = world.zone_ids
    assert ms["neighbours"] == {
        "in": sorted([ids["C1"], ids["C2"]]),
        "out": sorted([ids["C1"], ids["C2"]]),
    }
    # G2 is an exit-only gate: OUTSIDE is not listed, it shows as is_exit instead
    g2 = zones["G2"]
    assert (g2["is_entry"], g2["is_exit"]) == (False, True)
    assert g2["neighbours"] == {"in": [ids["C2"]], "out": [ids["C2"]]}


def test_connections_list_uses_null_for_outside(world: World) -> None:
    r = world.client.get(f"/api/venues/{world.venue_id}/connections")
    conns = r.json()["connections"]
    assert len(conns) == 10
    exit_gate = [c for c in conns if c["to_zone_id"] is None]
    assert exit_gate == [
        {**exit_gate[0], "from_zone_id": world.zone_ids["G2"], "bidirectional": False}
    ]


def test_graph_validate(world: World) -> None:
    r = world.client.get(f"/api/venues/{world.venue_id}/graph/validate")
    assert r.json() == {"venue_id": world.venue_id, "valid": True, "issues": []}


def test_unknown_venue_is_404(world: World) -> None:
    for path in ("", "/zones", "/connections", "/graph/validate"):
        r = world.client.get(f"/api/venues/999999999{path}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


# ------------------------------------------------------------------ events
def test_event_detail(world: World) -> None:
    r = world.client.get(f"/api/events/{world.event_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PLANNED" and body["is_synthetic"] is True
    assert body["start_time"] == "2027-03-12T10:30:00Z"
    assert (body["zone_count"], body["camera_count"], body["schedule_item_count"]) == (8, 0, 9)
    assert body["active_model"] is None
    assert "created_by" not in body  # no users (D7)


def test_event_list_pagination(world: World) -> None:
    first = world.client.get("/api/events", params={"limit": 1}).json()
    assert len(first["events"]) == 1
    assert first["events"][0]["event_id"] == world.event_id  # newest first
    if first["next_cursor"] is not None:
        second = world.client.get(
            "/api/events", params={"limit": 1, "cursor": first["next_cursor"]}
        ).json()
        assert second["events"][0]["event_id"] < world.event_id
    bad = world.client.get("/api/events", params={"limit": 501})
    assert bad.status_code == 422


def test_schedule_in_start_order(world: World) -> None:
    items = world.client.get(f"/api/events/{world.event_id}/schedule").json()["items"]
    assert len(items) == 9
    starts = [i["start_time"] for i in items]
    assert starts == sorted(starts)
    headline = next(i for i in items if i["title"] == "Headline band")
    assert headline["zone_code"] == "MS" and headline["attraction_weight"] == 0.95
    assert items[0]["zone_id"] is None and items[0]["category"] == "ENTRY_OPEN"


# ------------------------------------------------------------------ status transitions (§3.4)
def test_status_planned_live_ended(world: World) -> None:
    url = f"/api/events/{world.event_id}"
    r = world.client.patch(url, json={"status": "LIVE"})
    assert r.status_code == 200 and r.json()["status"] == "LIVE"
    r = world.client.patch(url, json={"status": "ENDED"})
    assert r.status_code == 200 and r.json()["status"] == "ENDED"
    audit = world.session.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == world.event_id, AuditLog.action == "EVENT_STATUS"
        )
    ).all()
    assert [a.details for a in audit] == [
        {"from": "PLANNED", "to": "LIVE"},
        {"from": "LIVE", "to": "ENDED"},
    ]


@pytest.mark.parametrize("target", ["PLANNED", "ENDED"])
def test_invalid_transition_is_409(world: World, target: str) -> None:
    r = world.client.patch(f"/api/events/{world.event_id}", json={"status": target})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"


def test_going_live_needs_valid_graph(world: World) -> None:
    # Break the graph: remove the connection to the facilities zone, which isolates WC.
    wc = world.zone_ids["WC"]
    world.session.execute(
        delete(ZoneConnection).where(
            (ZoneConnection.from_zone_id == wc) | (ZoneConnection.to_zone_id == wc)
        )
    )
    r = world.client.patch(f"/api/events/{world.event_id}", json={"status": "LIVE"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["message"] == "venue graph is not valid"
    assert err["details"] == [{"field": "WC", "issue": "ISOLATED: zone has no connections"}]
    assert world.client.get(f"/api/events/{world.event_id}").json()["status"] == "PLANNED"


def test_bad_status_value_is_422(world: World) -> None:
    r = world.client.patch(f"/api/events/{world.event_id}", json={"status": "PAUSED"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"

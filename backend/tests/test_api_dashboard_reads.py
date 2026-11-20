"""Dashboard read API: current, history, predictions, alerts + actions (WORKFLOW 4.4)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from crowdcast.api.app import create_app
from crowdcast.api.deps import get_session
from crowdcast.common.enums import DataOrigin
from crowdcast.forecasting.interfaces import run_cycle
from crowdcast.storage.interfaces import load_event, load_venue, repository
from crowdcast.storage.models import AuditLog
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
T0 = datetime(2027, 3, 12, 12, 0, tzinfo=UTC)


@dataclass
class World:
    client: TestClient
    session: Session
    event_id: int
    zone_ids: dict[str, int]


def _post(session: Session, event_id: int, zone_ids: dict[str, int], minute: int, ms: int) -> None:
    rows = [
        {
            "zone_id": zid,
            "bucket_start": T0 + timedelta(minutes=minute),
            "occupancy": ms if code == "MS" else 10 + minute,
            "occupancy_raw": None,
            "inflow": 3,
            "outflow": 2,
            "mean_speed_mps": 1.1,
            "quality": "OK",
            "method": "SIM_CLEAN",
        }
        for code, zid in zone_ids.items()
    ]
    repository.upsert_observations(session, event_id, DataOrigin.SYNTHETIC, rows)


@pytest.fixture
def world(db_session: Session) -> Iterator[World]:
    cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    cfg = cfg.model_copy(
        update={"venue": cfg.venue.model_copy(update={"name": f"Dash {uuid.uuid4().hex[:8]}"})}
    )
    zone_ids = load_venue(db_session, cfg).zone_ids
    event_id = load_event(
        db_session, load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml"), cfg
    ).event_id
    # 10 minutes: MS climbs into HIGH (u >= 0.8) from minute 6
    for m in range(10):
        _post(db_session, event_id, zone_ids, m, 2000 + 100 * m)
        run_cycle(db_session, event_id, T0 + timedelta(minutes=m + 1))
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield World(client, db_session, event_id, zone_ids)


# ------------------------------------------------------------------ 4.4.1
def test_current_state(world: World) -> None:
    body = world.client.get(f"/api/crowd/current/{world.event_id}").json()
    assert body["as_of"] == "2027-03-12T12:10:00Z"  # end of the newest bucket (event time)
    zones = {z["code"]: z for z in body["zones"]}
    ms = zones["MS"]
    assert ms["occupancy"] == 2900 and ms["occupancy_ratio"] == pytest.approx(2900 / 3000)
    assert ms["level"] == "CRITICAL" and ms["staleness_s"] == 0
    assert ms["density_ppm2"] == pytest.approx(2900 / 2000)
    assert ms["data_origin"] == "SYNTHETIC"


def test_history_one_and_five_minutes(world: World) -> None:
    ms = world.zone_ids["MS"]
    one = world.client.get(f"/api/crowd/history/{world.event_id}", params={"zone_id": ms}).json()
    assert one["origin"] == "SYNTHETIC" and len(one["series"]) == 1
    assert [p["occupancy"] for p in one["series"][0]["points"]] == [
        2000 + 100 * m for m in range(10)
    ]
    five = world.client.get(
        f"/api/crowd/history/{world.event_id}", params={"zone_id": ms, "resolution": "5m"}
    ).json()
    pts = five["series"][0]["points"]
    assert [p["occupancy"] for p in pts] == [2400, 2900]  # last value in each 5-min block
    assert [p["inflow"] for p in pts] == [15, 15]  # flows summed


def test_history_validation(world: World) -> None:
    url = f"/api/crowd/history/{world.event_id}"
    r = world.client.get(url, params={"from": "2027-03-12T12:00:00Z", "to": "2027-03-12T11:00:00Z"})
    assert r.status_code == 422
    r = world.client.get(url, params={"from": "2027-03-10T00:00:00Z", "to": "2027-03-12T00:00:00Z"})
    assert r.status_code == 422 and "24 h" in r.json()["error"]["message"]


# ------------------------------------------------------------------ 4.4.2 predictions
def test_latest_predictions(world: World) -> None:
    body = world.client.get(f"/api/predictions/{world.event_id}").json()
    assert body["issued_at"] == "2027-03-12T12:10:00Z"
    assert body["model"]["name"] == "B0_persistence"
    ms = next(z for z in body["zones"] if z["code"] == "MS")
    assert ms["current"]["occupancy"] == 2900
    assert [f["horizon_min"] for f in ms["forecasts"]] == [5, 15, 30]
    assert all(f["p50"] == 2900 and f["is_fallback"] for f in ms["forecasts"])


def test_zone_timeline_joins_actuals(world: World) -> None:
    ms = world.zone_ids["MS"]
    body = world.client.get(
        f"/api/predictions/{world.event_id}/zones/{ms}", params={"horizon_min": 5}
    ).json()
    pts = body["points"]
    assert all(p["horizon_min"] == 5 for p in pts)
    # issued 12:01 -> target 12:06 = end of bucket 12:05, whose occupancy is 2500
    first = next(p for p in pts if p["issued_at"] == "2027-03-12T12:01:00Z")
    assert first["p50"] == 2000 and first["actual"] == 2500
    # targets beyond the data have no actual yet
    assert pts[-1]["actual"] is None
    bad = world.client.get(
        f"/api/predictions/{world.event_id}/zones/{ms}", params={"horizon_min": 10}
    )
    assert bad.status_code == 422


def test_predictions_before_any_cycle(world: World, db_session: Session) -> None:
    venue = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    other = venue.model_copy(
        update={"venue": venue.venue.model_copy(update={"name": f"Empty {uuid.uuid4().hex[:6]}"})}
    )
    load_venue(db_session, other)
    eid = load_event(
        db_session, load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml"), other
    ).event_id
    body = world.client.get(f"/api/predictions/{eid}").json()
    assert body == {"event_id": eid, "issued_at": None, "model": None, "zones": []}


# ------------------------------------------------------------------ 4.4.2 alerts
def test_alert_list_and_filters(world: World) -> None:
    body = world.client.get(f"/api/alerts/{world.event_id}").json()
    kinds = {(a["zone_code"], a["alert_type"]) for a in body["alerts"]}
    assert ("MS", "CURRENT") in kinds and ("MS", "PREDICTED") in kinds
    only_current = world.client.get(
        f"/api/alerts/{world.event_id}", params={"status": "OPEN", "level": "CRITICAL"}
    ).json()["alerts"]
    assert all(a["status"] == "OPEN" and a["level"] == "CRITICAL" for a in only_current)
    page = world.client.get(f"/api/alerts/{world.event_id}", params={"limit": 1}).json()
    assert len(page["alerts"]) == 1 and page["next_cursor"] is not None


def test_acknowledge_then_resolve_with_audit(world: World) -> None:
    alert = world.client.get(f"/api/alerts/{world.event_id}").json()["alerts"][0]
    url = f"/api/alerts/{alert['alert_id']}"
    r = world.client.post(f"{url}/acknowledge", json={"note": "Two stewards sent"})
    assert r.status_code == 200 and r.json()["status"] == "ACKNOWLEDGED"
    assert r.json()["acknowledged_at"] is not None
    assert world.client.post(f"{url}/acknowledge").status_code == 409  # already acknowledged
    r = world.client.post(f"{url}/resolve")
    assert r.status_code == 200 and r.json()["status"] == "RESOLVED"
    assert r.json()["auto_resolved"] is False
    assert world.client.post(f"{url}/resolve").status_code == 409
    audit = world.session.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == alert["alert_id"],
            AuditLog.action.in_(["ALERT_ACK", "ALERT_RESOLVE"]),
        )
    ).all()
    assert [a.actor for a in audit] == ["USER", "USER"]
    assert audit[0].details is not None and audit[0].details["note"] == "Two stewards sent"


def test_unknown_ids_are_404(world: World) -> None:
    assert world.client.get("/api/crowd/current/999999999").status_code == 404
    assert world.client.get("/api/alerts/999999999").status_code == 404
    assert world.client.post("/api/alerts/999999999/acknowledge").status_code == 404

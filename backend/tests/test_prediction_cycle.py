"""Prediction cycle tests (WORKFLOW 4.2.1-4.2.3; doc 10 §12). Need the db container."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crowdcast.common.enums import CongestionLevel, DataOrigin
from crowdcast.forecasting.interfaces import run_cycle
from crowdcast.storage.interfaces import load_event, load_venue, repository
from crowdcast.storage.models import ModelVersion, Prediction
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
T0 = datetime(2027, 3, 12, 12, 0, tzinfo=UTC)  # inside the example event window


@dataclass
class World:
    session: Session
    event_id: int
    zone_ids: dict[str, int]

    def observe(self, code: str, minute: int, occupancy: int, origin: str = "SYNTHETIC") -> None:
        repository.upsert_observations(
            self.session,
            self.event_id,
            DataOrigin(origin),
            [
                {
                    "zone_id": self.zone_ids[code],
                    "bucket_start": T0 + timedelta(minutes=minute),
                    "occupancy": occupancy,
                    "occupancy_raw": None,
                    "inflow": 0,
                    "outflow": 0,
                    "mean_speed_mps": None,
                    "quality": "OK",
                    "method": "SIM_CLEAN" if origin == "SYNTHETIC" else "DETECTION",
                }
            ],
        )

    def predictions(self, issued: datetime) -> list[Prediction]:
        stmt = select(Prediction).where(
            Prediction.event_id == self.event_id, Prediction.issued_at == issued
        )
        return list(self.session.scalars(stmt))


@pytest.fixture
def world(db_session: Session) -> World:
    cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    cfg = cfg.model_copy(
        update={"venue": cfg.venue.model_copy(update={"name": f"Cycle {uuid.uuid4().hex[:8]}"})}
    )
    v = load_venue(db_session, cfg)
    e = load_event(
        db_session, load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml"), cfg
    )  # is_synthetic = true
    return World(db_session, e.event_id, v.zone_ids)


def _fill_all(w: World, minutes: range, occupancy: int = 100) -> None:
    for code in w.zone_ids:
        for m in minutes:
            w.observe(code, m, occupancy)


def test_cycle_writes_persistence_fallback_for_every_zone_and_horizon(world: World) -> None:
    _fill_all(world, range(10))
    world.observe("MS", 9, 2400)  # MS: u = 2400 / 3000 = 0.80 -> HIGH
    issued = T0 + timedelta(minutes=10)
    result = run_cycle(world.session, world.event_id, issued)
    assert result.written == 8 * 3 and result.skipped_zones == {}
    preds = world.predictions(issued)
    assert {(p.horizon_min, p.target_time - p.issued_at) for p in preds} == {
        (h, timedelta(minutes=h)) for h in (5, 15, 30)
    }
    assert all(p.is_fallback and p.p10 == p.p50 == p.p90 for p in preds)
    ms = [p for p in preds if p.zone_id == world.zone_ids["MS"]]
    assert {p.p50 for p in ms} == {2400.0}
    assert {p.predicted_level for p in ms} == {CongestionLevel.HIGH}
    # (0.8 - 0.6) / 0.35 * 0.75 + 0.25 * [0.8 >= 0.8] = 0.42857 + 0.25
    assert ms[0].risk_score == pytest.approx(0.67857, abs=1e-4)
    model = world.session.get(ModelVersion, preds[0].model_version_id)
    assert model is not None and model.model_family == "PERSISTENCE" and not model.is_active


def test_cycle_sees_only_buckets_that_ended_before_issue_time(world: World) -> None:
    _fill_all(world, range(5), occupancy=50)
    world.observe("C1", 5, 999)  # bucket 12:05 ends at 12:06: not visible at 12:05
    run_cycle(world.session, world.event_id, T0 + timedelta(minutes=5))
    c1 = [
        p for p in world.predictions(T0 + timedelta(minutes=5)) if p.zone_id == world.zone_ids["C1"]
    ]
    assert {p.p50 for p in c1} == {50.0}


def test_short_gap_is_forward_filled_but_stale_zone_is_skipped(world: World) -> None:
    _fill_all(world, range(3), occupancy=40)  # last bucket 12:02
    world.observe("MS", 9, 70)  # MS is current, everyone else is 7 min old at 12:10
    world.observe("C1", 7, 80)  # C1: 2-min gap at 12:10 -> forward-filled
    result = run_cycle(world.session, world.event_id, T0 + timedelta(minutes=10))
    assert set(result.fallback_zones) == {"MS", "C1"}
    assert set(result.skipped_zones) == set(world.zone_ids) - {"MS", "C1"}
    assert "7 min old" in result.skipped_zones["FC"]


def test_rerunning_a_cycle_updates_instead_of_duplicating(world: World) -> None:
    _fill_all(world, range(3))
    issued = T0 + timedelta(minutes=3)
    run_cycle(world.session, world.event_id, issued)
    world.observe("MS", 2, 555)  # late correction of the last bucket
    run_cycle(world.session, world.event_id, issued)
    assert len(world.predictions(issued)) == 24
    ms = [p for p in world.predictions(issued) if p.zone_id == world.zone_ids["MS"]]
    world.session.expire_all()
    assert {p.p50 for p in ms} == {555.0}


def test_real_observations_are_not_used_for_a_synthetic_event(world: World) -> None:
    world.observe("MS", 0, 123, origin="REAL")
    result = run_cycle(world.session, world.event_id, T0 + timedelta(minutes=1))
    assert result.written == 0 and "MS" in result.skipped_zones


def test_fallback_is_logged(world: World, caplog: pytest.LogCaptureFixture) -> None:
    _fill_all(world, range(2))
    with caplog.at_level(logging.INFO, logger="crowdcast.forecasting"):
        run_cycle(world.session, world.event_id, T0 + timedelta(minutes=2))
    assert "B0 fallback for 8 zones" in caplog.text


def test_baseline_model_row_is_reused(world: World) -> None:
    _fill_all(world, range(2))
    run_cycle(world.session, world.event_id, T0 + timedelta(minutes=1))
    run_cycle(world.session, world.event_id, T0 + timedelta(minutes=2))
    count = world.session.scalar(
        select(func.count()).select_from(ModelVersion).where(ModelVersion.name == "B0_persistence")
    )
    assert count == 1


def test_issue_time_must_be_minute_aligned(world: World) -> None:
    with pytest.raises(ValueError, match="minute boundary"):
        run_cycle(world.session, world.event_id, T0 + timedelta(seconds=30))

"""Model activation and model-driven prediction cycles (WORKFLOW 5.3.3; doc 14 §3.15).

A tiny A1 model is trained inside the test on one CROWDSIM run (SYNTHETIC) so the real
FeatureBuilder -> booster -> cycle path is exercised without the full training pipeline.
"""

from __future__ import annotations

import logging
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
from crowdcast.forecasting.features import (
    FeatureSet,
    History,
    add_target,
    build_features,
    feature_columns,
)
from crowdcast.forecasting.interfaces import HORIZONS, run_cycle
from crowdcast.forecasting.sources import published_schedule, venue_info
from crowdcast.forecasting.xgb import save_model, train_booster
from crowdcast.storage.interfaces import (
    ModelVersion,
    Prediction,
    load_event,
    load_venue,
    repository,
)
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config
from tools.crowdsim.params import load_regime
from tools.crowdsim.run import event_rng
from tools.crowdsim.sim import simulate

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
EVENT_FILE = CONFIGS / "events" / "v1_spring_fest_day1.yaml"


@pytest.fixture(scope="module")
def tiny_model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    venue_cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    event = load_event_config(EVENT_FILE)
    info = venue_info(venue_cfg)
    boosters, best = {}, {}
    cols: list[str] = []
    for h in HORIZONS:
        frames = []
        for seed in (0, 1):
            r = simulate(venue_cfg, event, load_regime("a"), event_rng(2027, seed))
            hist = History(
                n=r.occupancy.astype(float),
                inflow=r.inflow.astype(float),
                outflow=r.outflow.astype(float),
                speed=r.mean_speed_mps.astype(float),
                offset=0,
                duration_min=420.0,
                schedule=published_schedule(event, info.codes),
            )
            frames.append(add_target(build_features(hist, info, FeatureSet.A1, h), hist, info, h))
        train, val = frames
        cols = feature_columns(train)
        b = train_booster(
            train[cols], train["y"], val[cols], val["y"], seed=2027, params={"max_depth": 3}
        )
        boosters[h], best[str(h)] = b, int(b.best_iteration)
    path = tmp_path_factory.mktemp("model") / "xgb_A1_test"
    save_model(
        path,
        boosters,
        {
            "horizons": list(HORIZONS),
            "best_iteration": best,
            "feature_set": "A1",
            "feature_columns": cols,
            "outflow_shares": {},
        },
    )
    return path


@dataclass
class World:
    client: TestClient
    session: Session
    event_id: int
    zone_ids: dict[str, int]
    start: datetime


@pytest.fixture
def world(db_session: Session) -> Iterator[World]:
    cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    cfg = cfg.model_copy(
        update={"venue": cfg.venue.model_copy(update={"name": f"Model {uuid.uuid4().hex[:8]}"})}
    )
    zone_ids = load_venue(db_session, cfg).zone_ids
    event_id = load_event(db_session, load_event_config(EVENT_FILE), cfg).event_id
    # deactivate any model left active in the dev DB, inside this rolled-back transaction
    for m in db_session.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True))):
        m.is_active = False
    db_session.flush()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield World(
            client, db_session, event_id, zone_ids, datetime(2027, 3, 12, 10, 30, tzinfo=UTC)
        )


def _register(session: Session, path: Path, family: str = "XGBOOST") -> int:
    mv = ModelVersion(
        name=f"test_{uuid.uuid4().hex[:6]}",
        version="t",
        model_family=family,
        feature_set="A1",
        artifact_path=str(path),
        is_active=False,
    )
    session.add(mv)
    session.flush()
    return mv.model_version_id


def _observe(w: World, minutes: range) -> None:
    rows = [
        {
            "zone_id": zid,
            "bucket_start": w.start + timedelta(minutes=m),
            "occupancy": 50 + m,
            "occupancy_raw": None,
            "inflow": 3,
            "outflow": 2,
            "mean_speed_mps": 1.2,
            "quality": "OK",
            "method": "SIM_CLEAN",
        }
        for m in minutes
        for zid in w.zone_ids.values()
    ]
    repository.upsert_observations(w.session, w.event_id, DataOrigin.SYNTHETIC, rows)


def test_activate_then_cycle_uses_the_model(world: World, tiny_model_dir: Path) -> None:
    mid = _register(world.session, tiny_model_dir)
    r = world.client.post(f"/api/models/{mid}/activate")
    assert r.status_code == 200 and r.json() == {
        "model_version_id": mid,
        "is_active": True,
        "previous_active": None,
    }
    _observe(world, range(30))
    result = run_cycle(world.session, world.event_id, world.start + timedelta(minutes=30))
    assert result.fallback_zones == [] and len(result.model_zones) == 8
    preds = world.session.scalars(
        select(Prediction).where(Prediction.event_id == world.event_id)
    ).all()
    assert len(preds) == 24 and all(not p.is_fallback and p.model_version_id == mid for p in preds)
    assert all(0 <= p.p10 <= p.p50 <= p.p90 for p in preds)


def test_cold_start_falls_back_to_persistence(world: World, tiny_model_dir: Path) -> None:
    world.client.post(f"/api/models/{_register(world.session, tiny_model_dir)}/activate")
    _observe(world, range(10))
    result = run_cycle(world.session, world.event_id, world.start + timedelta(minutes=10))
    assert len(result.fallback_zones) == 8 and "cold start" in (result.fallback_reason or "")


def test_broken_model_falls_back_and_logs(
    world: World, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text('{"horizons": [5, 15, 30]}', encoding="utf-8")
    mid = _register(world.session, broken)
    mv = world.session.get(ModelVersion, mid)
    assert mv is not None
    mv.is_active = True  # bypass activation checks to simulate a model that breaks later
    world.session.flush()
    _observe(world, range(30))
    with caplog.at_level(logging.INFO, logger="crowdcast.forecasting"):
        result = run_cycle(world.session, world.event_id, world.start + timedelta(minutes=30))
    assert len(result.fallback_zones) == 8 and "failed" in (result.fallback_reason or "")
    assert "B0 fallback" in caplog.text


def test_activation_switches_and_validates(world: World, tiny_model_dir: Path) -> None:
    first = _register(world.session, tiny_model_dir)
    second = _register(world.session, tiny_model_dir)
    world.client.post(f"/api/models/{first}/activate")
    r = world.client.post(f"/api/models/{second}/activate")
    assert r.json()["previous_active"] == first
    active = world.session.scalars(
        select(ModelVersion).where(ModelVersion.is_active.is_(True))
    ).all()
    assert [m.model_version_id for m in active] == [second]
    missing = _register(world.session, tiny_model_dir.parent / "does_not_exist")
    r = world.client.post(f"/api/models/{missing}/activate")
    assert r.status_code == 422 and r.json()["error"]["details"][0]["issue"] == (
        "missing manifest.json"
    )
    persistence = _register(world.session, tiny_model_dir, family="PERSISTENCE")
    assert world.client.post(f"/api/models/{persistence}/activate").status_code == 422
    assert world.client.post("/api/models/999999999/activate").status_code == 404
    listed = world.client.get("/api/models").json()["models"]
    assert any(m["model_version_id"] == second and m["is_active"] for m in listed)

"""End-to-end: CROWDSIM run -> replay client -> ingestion API -> crowd_observations (3.4.3)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crowdcast.api.app import create_app
from crowdcast.api.deps import get_session
from crowdcast.storage.interfaces import load_event, load_venue
from crowdcast.storage.models import CrowdObservation
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config
from tools.crowdsim.output import write_run
from tools.crowdsim.params import load_regime
from tools.crowdsim.replay import replay
from tools.crowdsim.run import event_rng
from tools.crowdsim.sim import simulate

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
VENUE_FILE = CONFIGS / "venues" / "v1.yaml"
EVENT_FILE = CONFIGS / "events" / "v1_spring_fest_day1.yaml"


def test_replay_lands_in_crowd_observations(db_session: Session, tmp_path: Path) -> None:
    venue = load_venue_config(VENUE_FILE)
    event = load_event_config(EVENT_FILE)
    result = simulate(venue, event, load_regime("a"), event_rng(2027, 0))
    run_dir = write_run(
        result, tmp_path / "run", event_name="t", regime="A", master_seed=2027,
        event_index=0, venue_file=VENUE_FILE, event_file=EVENT_FILE,
    )  # fmt: skip

    named = venue.model_copy(
        update={"venue": venue.venue.model_copy(update={"name": f"Replay {uuid.uuid4().hex[:8]}"})}
    )
    load_venue(db_session, named)
    event_id = load_event(db_session, event, named).event_id

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    sleeps: list[float] = []
    with TestClient(app) as client:

        def call(path: str, body: dict[str, Any] | None) -> dict[str, Any]:
            r = client.get(path) if body is None else client.post(path, json=body)
            assert r.status_code == 200, r.text
            out: dict[str, Any] = r.json()
            return out

        totals = replay(
            run_dir, event_id, call, speedup=600, minutes_per_batch=10, sleep=sleeps.append
        )

    rows = len(result.bucket_starts) * len(result.zone_codes)
    assert totals == {
        "inserted": rows,
        "updated": 0,
        "rejected": 0,
        "requests": -(-len(result.bucket_starts) // 10),
    }
    assert sleeps and all(s == pytest.approx(1.0) for s in sleeps)  # 10 min at 600x = 1 s
    stored = db_session.scalar(
        select(func.count())
        .select_from(CrowdObservation)
        .where(CrowdObservation.event_id == event_id, CrowdObservation.data_origin == "SYNTHETIC")
    )
    assert stored == rows
    peak = db_session.scalar(
        select(func.max(CrowdObservation.occupancy)).where(CrowdObservation.event_id == event_id)
    )
    assert peak == int(np.max(result.occupancy))

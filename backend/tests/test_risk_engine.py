"""Risk engine against the database, driven through the prediction cycle (WORKFLOW 4.3.2-4.3.3).

With only the B0 fallback, the median forecast equals the current occupancy, so a zone that is
HIGH now opens a CURRENT alert at once and a PREDICTED alert one cycle later.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from crowdcast.common.enums import AlertStatus, AlertType, CongestionLevel, DataOrigin
from crowdcast.forecasting.interfaces import run_cycle
from crowdcast.storage.interfaces import CongestionAlert, load_event, load_venue, repository
from crowdcast.storage.models import AuditLog
from crowdcast.venue_graph.interfaces import load_event_config, load_venue_config

pytestmark = pytest.mark.db

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
T0 = datetime(2027, 3, 12, 12, 0, tzinfo=UTC)
MS_CAP = 3000


class Run:
    def __init__(self, session: Session) -> None:
        cfg = load_venue_config(CONFIGS / "venues" / "v1.yaml")
        cfg = cfg.model_copy(
            update={"venue": cfg.venue.model_copy(update={"name": f"Risk {uuid.uuid4().hex[:8]}"})}
        )
        self.session = session
        self.zone_ids = load_venue(session, cfg).zone_ids
        self.event_id = load_event(
            session, load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml"), cfg
        ).event_id
        self.minute = 0

    def step(self, ms_ratio: float) -> None:
        """Post one minute (MS at the given u, other zones quiet), then run the cycle."""
        rows = [
            {
                "zone_id": zid,
                "bucket_start": T0 + timedelta(minutes=self.minute),
                "occupancy": round(ms_ratio * MS_CAP) if code == "MS" else 10,
                "occupancy_raw": None,
                "inflow": 0,
                "outflow": 0,
                "mean_speed_mps": None,
                "quality": "OK",
                "method": "SIM_CLEAN",
            }
            for code, zid in self.zone_ids.items()
        ]
        repository.upsert_observations(self.session, self.event_id, DataOrigin.SYNTHETIC, rows)
        self.minute += 1
        run_cycle(self.session, self.event_id, T0 + timedelta(minutes=self.minute))

    def alerts(self) -> list[CongestionAlert]:
        stmt = (
            select(CongestionAlert)
            .where(CongestionAlert.event_id == self.event_id)
            .order_by(CongestionAlert.alert_id)
        )
        return list(self.session.scalars(stmt))

    def audit(self, action: str) -> list[AuditLog]:
        ids = [a.alert_id for a in self.alerts()]
        stmt = select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id.in_(ids))
        return list(self.session.scalars(stmt))


@pytest.fixture
def run(db_session: Session) -> Run:
    return Run(db_session)


def test_current_opens_at_once_predicted_after_two_cycles(run: Run) -> None:
    run.step(0.5)
    run.step(0.85)
    assert [(a.alert_type, a.level) for a in run.alerts()] == [
        (AlertType.CURRENT, CongestionLevel.HIGH)
    ]
    run.step(0.85)
    alerts = run.alerts()
    assert [a.alert_type for a in alerts] == [AlertType.CURRENT, AlertType.PREDICTED]
    predicted = alerts[1]
    assert predicted.horizon_min == 5  # smallest horizon (persistence: all horizons equal)
    assert predicted.predicted_onset == predicted.opened_at + timedelta(minutes=5)
    assert predicted.prediction_id is not None
    assert predicted.opened_at == T0 + timedelta(minutes=3)  # event time, not wall clock
    assert "Main Stage" in alerts[0].message and "85%" in alerts[0].message


def test_escalation_is_logged_on_the_same_alert(run: Run) -> None:
    run.step(0.85)
    run.step(0.97)
    current = [a for a in run.alerts() if a.alert_type is AlertType.CURRENT]
    assert len(current) == 1 and current[0].level is CongestionLevel.CRITICAL
    assert len(run.audit("ALERT_ESCALATE")) >= 1


def test_auto_resolve_after_three_low_cycles(run: Run) -> None:
    run.step(0.85)
    run.step(0.85)
    for _ in range(3):
        run.step(0.5)
    alerts = run.alerts()
    assert alerts and all(a.status is AlertStatus.RESOLVED and a.auto_resolved for a in alerts)
    assert all(a.resolved_at == T0 + timedelta(minutes=5) for a in alerts)
    assert len(run.audit("ALERT_AUTO_RESOLVE")) == len(alerts)


def test_flapping_occupancy_keeps_one_alert(run: Run) -> None:
    for k in range(12):
        run.step(0.81 if k % 2 else 0.79)
    current = [a for a in run.alerts() if a.alert_type is AlertType.CURRENT]
    assert len(current) == 1 and current[0].status is AlertStatus.OPEN


def test_rerunning_a_cycle_does_not_duplicate_alerts(run: Run) -> None:
    run.step(0.85)
    run_cycle(run.session, run.event_id, T0 + timedelta(minutes=1))
    assert len(run.alerts()) == 1

"""Alert list and operator actions (doc 14 §3.13-3.14, amended in §6).

Acknowledge / resolve are real operator actions, so they are stamped with the wall clock (UTC).
There are no users (D7): ``acknowledged_by`` is not returned and the audit actor is USER. The
optional note has no column and is kept in the audit entry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.common.enums import AlertStatus, AlertType, CongestionLevel
from crowdcast.common.time import utc_now
from crowdcast.storage.interfaces import CongestionAlert, repository

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    alert_id: int
    zone_id: int
    zone_code: str
    alert_type: AlertType
    level: CongestionLevel
    horizon_min: int | None
    predicted_onset: datetime | None
    trigger_value: float | None
    status: AlertStatus
    message: str
    opened_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    auto_resolved: bool


class AlertList(BaseModel):
    alerts: list[AlertOut]
    next_cursor: str | None


class Note(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(None, max_length=500)


def _out(a: CongestionAlert, codes: dict[int, str]) -> AlertOut:
    return AlertOut(
        alert_id=a.alert_id, zone_id=a.zone_id, zone_code=codes.get(a.zone_id, "?"),
        alert_type=a.alert_type, level=a.level, horizon_min=a.horizon_min,
        predicted_onset=a.predicted_onset, trigger_value=a.trigger_value, status=a.status,
        message=a.message, opened_at=a.opened_at, acknowledged_at=a.acknowledged_at,
        resolved_at=a.resolved_at, auto_resolved=a.auto_resolved,
    )  # fmt: skip


def _zone_codes(session: SessionDep, event_id: int) -> dict[int, str]:
    event = repository.get_event(session, event_id)
    if event is None:
        raise ApiError(404, "NOT_FOUND", f"event {event_id} not found")
    return {z.zone_id: z.code for z in repository.list_zones(session, event.venue_id)}


@router.get("/{event_id}", response_model=AlertList)
def list_alerts(
    event_id: int,
    session: SessionDep,
    status: Annotated[list[AlertStatus] | None, Query()] = None,
    level: CongestionLevel | None = None,
    zone_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: Annotated[str | None, Query(pattern=r"^\d+$")] = None,
) -> AlertList:
    """Newest first; filter by status (repeatable), level and zone (doc 14 §3.13)."""
    codes = _zone_codes(session, event_id)
    rows = repository.list_alerts(
        session, event_id, statuses=status, level=None if level is None else level.value,
        zone_id=zone_id, limit=limit + 1, before_id=None if cursor is None else int(cursor),
    )  # fmt: skip
    page = rows[:limit]
    return AlertList(
        alerts=[_out(a, codes) for a in page],
        next_cursor=str(page[-1].alert_id) if len(rows) > limit else None,
    )


def _act(session: SessionDep, alert_id: int, action: str, note: str | None) -> AlertOut:
    alert = repository.get_alert(session, alert_id)
    if alert is None:
        raise ApiError(404, "NOT_FOUND", f"alert {alert_id} not found")
    now = utc_now()
    if action == "ALERT_ACK":
        if alert.status is not AlertStatus.OPEN:
            raise ApiError(409, "CONFLICT", f"cannot acknowledge a {alert.status.value} alert")
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
    else:
        if alert.status is AlertStatus.RESOLVED:
            raise ApiError(409, "CONFLICT", "alert is already resolved")
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now
        alert.auto_resolved = False
    repository.add_audit(
        session, action, "alert", alert.alert_id,
        {"note": note, "status": alert.status.value}, actor="USER",
    )  # fmt: skip
    session.flush()
    return _out(alert, _zone_codes(session, alert.event_id))


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: int, session: SessionDep, body: Note | None = None) -> AlertOut:
    return _act(session, alert_id, "ALERT_ACK", None if body is None else body.note)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: int, session: SessionDep, body: Note | None = None) -> AlertOut:
    return _act(session, alert_id, "ALERT_RESOLVE", None if body is None else body.note)

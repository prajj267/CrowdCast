"""Risk engine, database part (doc 08 M7; WORKFLOW 4.3.2). Called by the prediction cycle.

For one event and issue time it rebuilds the last 3 cycles of signals per zone from stored
observations (CURRENT) and predictions (PREDICTED), asks ``alerts.decide`` what to do, and
opens, escalates or auto-resolves ``congestion_alerts``. Escalations and auto-resolutions are
written to ``audit_log``. All timestamps are event time (the cycle's issue time).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from crowdcast.common.enums import AlertStatus, AlertType, CongestionLevel, DataOrigin
from crowdcast.risk.alerts import RESOLVE_CYCLES, Action, CycleSignal, decide
from crowdcast.risk.levels import Thresholds
from crowdcast.storage.interfaces import CongestionAlert, Prediction, repository

ONE_MIN = timedelta(minutes=1)


@dataclass
class AlertChanges:
    opened: list[tuple[str, AlertType]] = field(default_factory=list)
    escalated: list[tuple[str, AlertType]] = field(default_factory=list)
    resolved: list[tuple[str, AlertType]] = field(default_factory=list)


def _forecast_rows(preds: list[Prediction]) -> dict[tuple[datetime, int, int], Prediction]:
    """One row per (issued_at, zone, horizon): a learned model's row wins over the fallback."""
    best: dict[tuple[datetime, int, int], Prediction] = {}
    for p in preds:
        key = (p.issued_at, p.zone_id, p.horizon_min)
        if key not in best or (best[key].is_fallback and not p.is_fallback):
            best[key] = p
    return best


def evaluate_alerts(
    session: Session, event_id: int, issued_at: datetime, origin: DataOrigin
) -> AlertChanges:
    event = repository.get_event(session, event_id)
    if event is None:
        raise LookupError(f"event {event_id} not found")
    zones = repository.list_zones(session, event.venue_id)
    cycles = [issued_at - k * ONE_MIN for k in range(RESOLVE_CYCLES - 1, -1, -1)]  # oldest first

    # CURRENT: occupancy at the end of the bucket that closed at each cycle time
    occ: dict[tuple[datetime, int], int] = {}
    for o in repository.observation_window(
        session, event_id, origin, cycles[0] - ONE_MIN, issued_at
    ):
        if o.occupancy is not None:
            occ[(o.bucket_start + ONE_MIN, o.zone_id)] = o.occupancy

    # PREDICTED: median forecast per horizon
    rows = _forecast_rows(repository.predictions_at(session, event_id, cycles))
    forecast: dict[tuple[datetime, int], dict[int, float]] = defaultdict(dict)
    for (t, zone_id, h), p in rows.items():
        forecast[(t, zone_id)][h] = p.p50

    open_alerts = {
        (a.zone_id, a.alert_type): a for a in repository.unresolved_alerts(session, event_id)
    }
    changes = AlertChanges()
    for z in zones:
        thr = Thresholds.from_overrides(
            z.threshold_elevated, z.threshold_high, z.threshold_critical
        )
        cap = float(z.planning_capacity)
        history = [
            CycleSignal(
                current_u=None if (c, z.zone_id) not in occ else occ[(c, z.zone_id)] / cap,
                forecast_u={h: v / cap for h, v in forecast[(c, z.zone_id)].items()} or None,
            )
            for c in cycles
        ]
        for kind in (AlertType.CURRENT, AlertType.PREDICTED):
            alert = open_alerts.get((z.zone_id, kind))
            d = decide(kind, history, None if alert is None else alert.level, thr)
            if d.action is Action.OPEN:
                assert d.level is not None and d.trigger_value is not None
                pred = (
                    None
                    if d.horizon_min is None
                    else rows.get((issued_at, z.zone_id, d.horizon_min))
                )
                session.add(
                    CongestionAlert(
                        event_id=event_id,
                        zone_id=z.zone_id,
                        alert_type=kind,
                        level=d.level,
                        horizon_min=d.horizon_min,
                        predicted_onset=None
                        if d.horizon_min is None
                        else issued_at + timedelta(minutes=d.horizon_min),
                        trigger_value=d.trigger_value,
                        status=AlertStatus.OPEN,
                        message=_message(z.name, kind, d.level, d.trigger_value, d.horizon_min),
                        opened_at=issued_at,
                        prediction_id=None if pred is None else pred.prediction_id,
                    )
                )
                changes.opened.append((z.code, kind))
            elif d.action is Action.ESCALATE and alert is not None:
                alert.level = CongestionLevel.CRITICAL
                repository.add_audit(
                    session, "ALERT_ESCALATE", "alert", alert.alert_id,
                    {"zone": z.code, "type": kind.value, "to": "CRITICAL",
                     "trigger_value": d.trigger_value, "at": issued_at.isoformat()},
                )  # fmt: skip
                changes.escalated.append((z.code, kind))
            elif d.action is Action.RESOLVE and alert is not None:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = issued_at
                alert.auto_resolved = True
                repository.add_audit(
                    session, "ALERT_AUTO_RESOLVE", "alert", alert.alert_id,
                    {"zone": z.code, "type": kind.value, "at": issued_at.isoformat()},
                )  # fmt: skip
                changes.resolved.append((z.code, kind))
    session.flush()
    return changes


def _message(
    zone: str, kind: AlertType, lvl: CongestionLevel, u: float, horizon: int | None
) -> str:
    pct = round(100 * u)
    if kind is AlertType.CURRENT:
        return f"{zone}: {lvl.value} now - occupancy at {pct}% of planning capacity"
    return f"{zone}: {lvl.value} forecast in {horizon} min - {pct}% of planning capacity"

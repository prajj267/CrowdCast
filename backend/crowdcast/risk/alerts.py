"""Alert state machine, pure part (doc 08 M7; WORKFLOW 4.3.2).

``decide`` looks at the last three cycles of one zone and one alert type and says what to do.
Nothing is stored between cycles: the caller rebuilds the recent history from observations and
predictions, so a re-run replay takes exactly the same decisions.

- CURRENT opens as soon as the current level is >= HIGH (no pending cycle).
- PREDICTED opens when the median forecast is >= HIGH at some horizon in two consecutive
  cycles (the first cycle is the "pending" state); it records the smallest such horizon.
- An open alert auto-resolves after 3 consecutive cycles below theta_HIGH - 0.05 (hysteresis).
  A cycle without data does not count as "below", so missing data never closes an alert.
- An open HIGH alert escalates to CRITICAL when the level reaches CRITICAL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from crowdcast.common.enums import AlertType, CongestionLevel
from crowdcast.risk.levels import Thresholds, at_least, level

RESOLVE_MARGIN = 0.05
RESOLVE_CYCLES = 3
PREDICTED_CONFIRM_CYCLES = 2


@dataclass(frozen=True)
class CycleSignal:
    """What one cycle saw for one zone. ``None`` = no data in that cycle.

    current_u: occupancy ratio now (CURRENT alerts).
    forecast_u: median forecast ratio per horizon in minutes (PREDICTED alerts).
    """

    current_u: float | None = None
    forecast_u: dict[int, float] | None = None


class Action(StrEnum):
    NONE = "NONE"
    OPEN = "OPEN"
    ESCALATE = "ESCALATE"
    RESOLVE = "RESOLVE"


@dataclass(frozen=True)
class Decision:
    action: Action
    level: CongestionLevel | None = None
    horizon_min: int | None = None  # PREDICTED: smallest horizon at >= HIGH
    trigger_value: float | None = None  # the u that triggered (or escalated) the alert


def _value(sig: CycleSignal, kind: AlertType) -> float | None:
    """The single ratio that drives this alert type (worst horizon for PREDICTED)."""
    if kind is AlertType.CURRENT:
        return sig.current_u
    return max(sig.forecast_u.values()) if sig.forecast_u else None


def _triggered(sig: CycleSignal, kind: AlertType, t: Thresholds) -> bool:
    v = _value(sig, kind)
    return v is not None and at_least(level(v, t), CongestionLevel.HIGH)


def decide(
    kind: AlertType,
    history: list[CycleSignal],
    open_level: CongestionLevel | None,
    t: Thresholds,
) -> Decision:
    """``history`` = recent cycles, oldest first, the current cycle last.

    ``open_level`` = level of the zone's unresolved alert of this type, or None if none is open.
    """
    if not history:
        return Decision(Action.NONE)
    now = history[-1]

    if open_level is None:
        need = 1 if kind is AlertType.CURRENT else PREDICTED_CONFIRM_CYCLES
        recent = history[-need:]
        if len(recent) < need or not all(_triggered(s, kind, t) for s in recent):
            return Decision(Action.NONE)
        if kind is AlertType.CURRENT:
            u = now.current_u
            assert u is not None
            return Decision(Action.OPEN, level(u, t), None, u)
        assert now.forecast_u is not None
        hits = sorted(
            h for h, u in now.forecast_u.items() if at_least(level(u, t), CongestionLevel.HIGH)
        )
        h = hits[0]
        u = now.forecast_u[h]
        return Decision(Action.OPEN, level(u, t), h, u)

    last = history[-RESOLVE_CYCLES:]
    below = t.high - RESOLVE_MARGIN
    values = [_value(s, kind) for s in last]
    if len(last) == RESOLVE_CYCLES and all(v is not None and v < below for v in values):
        return Decision(Action.RESOLVE)

    v = _value(now, kind)
    if (
        v is not None
        and open_level is not CongestionLevel.CRITICAL
        and level(v, t) is CongestionLevel.CRITICAL
    ):
        return Decision(Action.ESCALATE, CongestionLevel.CRITICAL, trigger_value=v)
    return Decision(Action.NONE)

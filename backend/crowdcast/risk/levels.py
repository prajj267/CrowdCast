"""Congestion level and risk score (doc 08 M7; doc 11 §4; WORKFLOW 4.3.1).

u = N / C is the occupancy ratio to planning capacity. Thresholds are per zone, with the
defaults 0.60 / 0.80 / 0.95 when the zone has no override (doc 13: NULL = default).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from crowdcast.common.enums import CongestionLevel

DEFAULT_ELEVATED = 0.60
DEFAULT_HIGH = 0.80
DEFAULT_CRITICAL = 0.95
RISK_LAMBDA = 0.25  # UI-ranking weight of the upper-quantile bonus, not learned (doc 08 M7)

LEVEL_ORDER = (
    CongestionLevel.NORMAL,
    CongestionLevel.ELEVATED,
    CongestionLevel.HIGH,
    CongestionLevel.CRITICAL,
)


@dataclass(frozen=True, slots=True)
class Thresholds:
    elevated: float = DEFAULT_ELEVATED
    high: float = DEFAULT_HIGH
    critical: float = DEFAULT_CRITICAL

    def __post_init__(self) -> None:
        if not 0 < self.elevated < self.high < self.critical:
            raise ValueError(f"thresholds must be increasing and > 0: {self}")

    @classmethod
    def from_overrides(
        cls,
        elevated: float | Decimal | None,
        high: float | Decimal | None,
        critical: float | Decimal | None,
    ) -> Thresholds:
        """Zone row values, where NULL means "use the default" (doc 13)."""
        return cls(
            DEFAULT_ELEVATED if elevated is None else float(elevated),
            DEFAULT_HIGH if high is None else float(high),
            DEFAULT_CRITICAL if critical is None else float(critical),
        )


def level(u: float, t: Thresholds = Thresholds()) -> CongestionLevel:
    """L(u): NORMAL < θE <= ELEVATED < θH <= HIGH < θC <= CRITICAL (lower bounds inclusive)."""
    if u >= t.critical:
        return CongestionLevel.CRITICAL
    if u >= t.high:
        return CongestionLevel.HIGH
    if u >= t.elevated:
        return CongestionLevel.ELEVATED
    return CongestionLevel.NORMAL


def at_least(lvl: CongestionLevel, floor: CongestionLevel) -> bool:
    return LEVEL_ORDER.index(lvl) >= LEVEL_ORDER.index(floor)


def risk_score(
    u50: float, u90: float, t: Thresholds = Thresholds(), lam: float = RISK_LAMBDA
) -> float:
    """r = min(1, max(0, (u50 - θE) / (θC - θE)) * (1 - λ) + λ * 1[u90 >= θH]) (doc 08 M7)."""
    base = max(0.0, (u50 - t.elevated) / (t.critical - t.elevated))
    bonus = 1.0 if u90 >= t.high else 0.0
    return min(1.0, base * (1 - lam) + lam * bonus)

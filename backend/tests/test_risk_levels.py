"""Level function and risk score (WORKFLOW 4.3.1; doc 17 TC-CNG-01..03)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from crowdcast.common.enums import CongestionLevel as L
from crowdcast.risk.levels import Thresholds, at_least, level, risk_score


def test_tc_cng_01_boundaries_with_default_thresholds() -> None:
    us = [0.599, 0.600, 0.799, 0.800, 0.949, 0.950]
    assert [level(u) for u in us] == [
        L.NORMAL, L.ELEVATED, L.ELEVATED, L.HIGH, L.HIGH, L.CRITICAL,
    ]  # fmt: skip


def test_tc_cng_02_zone_overrides_applied() -> None:
    t = Thresholds.from_overrides(Decimal("0.500"), None, Decimal("0.900"))
    assert (t.elevated, t.high, t.critical) == (0.5, 0.8, 0.9)
    assert level(0.55, t) is L.ELEVATED  # NORMAL under the defaults
    assert level(0.92, t) is L.CRITICAL  # HIGH under the defaults
    with pytest.raises(ValueError):
        Thresholds(0.9, 0.8, 0.95)


def test_tc_cng_03_risk_score_hand_computed() -> None:
    # (0.836 - 0.60) / 0.35 * 0.75 + 0.25 * [0.94 >= 0.80] = 0.5057 + 0.25 = 0.7557
    assert risk_score(0.836, 0.94) == pytest.approx(0.756, abs=1e-3)
    # below ELEVATED and upper quantile below HIGH -> 0
    assert risk_score(0.4, 0.7) == 0.0
    # only the upper-quantile bonus
    assert risk_score(0.5, 0.85) == pytest.approx(0.25)
    # capped at 1
    assert risk_score(1.4, 1.6) == 1.0


def test_level_order() -> None:
    assert at_least(L.CRITICAL, L.HIGH) and at_least(L.HIGH, L.HIGH)
    assert not at_least(L.ELEVATED, L.HIGH)

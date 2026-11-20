"""Alert state machine, pure part (WORKFLOW 4.3.2-4.3.3; doc 17 TC-ALR-01..06).

``simulate`` drives ``decide`` cycle by cycle like the engine does: the last 3 signals and the
level of the currently open alert (if any).
"""

from __future__ import annotations

from crowdcast.common.enums import AlertType, CongestionLevel
from crowdcast.risk.alerts import Action, CycleSignal, Decision, decide
from crowdcast.risk.levels import Thresholds

T = Thresholds()
CUR, PRED = AlertType.CURRENT, AlertType.PREDICTED


def simulate(kind: AlertType, signals: list[CycleSignal]) -> list[Decision]:
    """Run the machine over a sequence of cycles; returns the non-NONE decisions."""
    open_level: CongestionLevel | None = None
    out = []
    for k in range(len(signals)):
        d = decide(kind, signals[max(0, k - 2) : k + 1], open_level, T)
        if d.action is Action.OPEN or d.action is Action.ESCALATE:
            open_level = d.level
        elif d.action is Action.RESOLVE:
            open_level = None
        if d.action is not Action.NONE:
            out.append(d)
    return out


def cur(u: float | None) -> CycleSignal:
    return CycleSignal(current_u=u)


def pred(**by_h: float) -> CycleSignal:
    return CycleSignal(forecast_u={int(k[1:]): v for k, v in by_h.items()})


def test_tc_alr_01_one_predicted_cycle_is_not_enough() -> None:
    assert simulate(PRED, [pred(h15=0.85), pred(h15=0.5), pred(h15=0.5)]) == []


def test_tc_alr_02_two_consecutive_predicted_cycles_open_one_alert() -> None:
    out = simulate(PRED, [pred(h5=0.7, h15=0.85, h30=0.9), pred(h5=0.7, h15=0.82, h30=0.88)])
    assert out == [Decision(Action.OPEN, CongestionLevel.HIGH, 15, 0.82)]  # smallest horizon


def test_tc_alr_03_current_high_opens_immediately() -> None:
    assert simulate(CUR, [cur(0.5), cur(0.81)]) == [
        Decision(Action.OPEN, CongestionLevel.HIGH, None, 0.81)
    ]


def test_tc_alr_04_flapping_input_gives_at_most_one_alert() -> None:
    out = simulate(CUR, [cur(0.79 if k % 2 == 0 else 0.81) for k in range(20)])
    assert [d.action for d in out] == [Action.OPEN]  # 0.79 is never below 0.80 - 0.05


def test_tc_alr_05_open_alert_escalates_to_critical_once() -> None:
    out = simulate(CUR, [cur(0.85), cur(0.9), cur(0.97), cur(0.99)])
    assert [d.action for d in out] == [Action.OPEN, Action.ESCALATE]
    assert out[1].level is CongestionLevel.CRITICAL and out[1].trigger_value == 0.97


def test_tc_alr_06_three_cycles_below_threshold_minus_margin_resolve() -> None:
    signals = [cur(0.85), cur(0.74), cur(0.74), cur(0.76), cur(0.7), cur(0.7), cur(0.7)]
    out = simulate(CUR, signals)
    # 0.76 is not below 0.75, so the count restarts; resolves after the 3rd 0.7
    assert [d.action for d in out] == [Action.OPEN, Action.RESOLVE]


def test_missing_data_never_resolves_an_alert() -> None:
    out = simulate(CUR, [cur(0.9), cur(None), cur(None), cur(None), cur(0.5)])
    assert [d.action for d in out] == [Action.OPEN]


def test_predicted_resolves_on_worst_horizon() -> None:
    hi = pred(h5=0.85, h15=0.9)
    low_but_one = pred(h5=0.5, h15=0.77)  # worst horizon 0.77 is not below 0.75
    low = pred(h5=0.5, h15=0.6)
    out = simulate(PRED, [hi, hi, low_but_one, low, low, low])
    assert [d.action for d in out] == [Action.OPEN, Action.RESOLVE]


def test_alert_can_reopen_after_resolution() -> None:
    signals = [cur(0.9), cur(0.5), cur(0.5), cur(0.5), cur(0.9)]
    assert [d.action for d in simulate(CUR, signals)] == [Action.OPEN, Action.RESOLVE, Action.OPEN]


def test_zone_overrides_change_the_trigger() -> None:
    strict = Thresholds(0.4, 0.5, 0.7)
    assert decide(CUR, [cur(0.55)], None, strict).action is Action.OPEN
    assert decide(CUR, [cur(0.55)], None, T).action is Action.NONE

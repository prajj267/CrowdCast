"""Tests for the event + published schedule YAML format v1 (task 2.1.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from crowdcast.common.enums import ScheduleCategory
from crowdcast.venue_graph.interfaces import EventConfig, load_event_config, load_venue_config

CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def _minimal() -> dict[str, Any]:
    return {
        "format_version": 1,
        "illustrative": True,
        "event": {
            "name": "Test day",
            "venue": "v1",
            "start_time": "2027-03-12T10:00:00Z",
            "end_time": "2027-03-12T18:00:00Z",
            "expected_attendance": 1000,
        },
        "schedule": [
            {"title": "Show", "category": "PERFORMANCE", "zone": "MS",
             "start": "2027-03-12T14:00:00Z", "end": "2027-03-12T15:00:00Z"},
        ],
    }  # fmt: skip


def _invalid(data: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        EventConfig.model_validate(data)


def test_minimal_event_parses_with_defaults() -> None:
    cfg = EventConfig.model_validate(_minimal())
    item = cfg.schedule[0]
    assert item.category is ScheduleCategory.PERFORMANCE
    assert item.attraction_weight == 0.5  # default, as in the DB column
    assert cfg.event.is_synthetic is False
    assert item.start == datetime(2027, 3, 12, 14, tzinfo=UTC)


def test_offset_times_are_converted_to_utc() -> None:
    data = _minimal()
    data["event"]["start_time"] = "2027-03-12T15:30:00+05:30"  # = 10:00 UTC
    cfg = EventConfig.model_validate(data)
    assert cfg.event.start_time == datetime(2027, 3, 12, 10, tzinfo=UTC)
    assert cfg.event.start_time.utcoffset() is not None
    assert cfg.event.start_time.tzinfo is UTC


def test_naive_times_are_rejected() -> None:
    data = _minimal()
    data["schedule"][0]["start"] = "2027-03-12T14:00:00"  # no time zone
    _invalid(data, "timezone")


def test_event_window_rules() -> None:
    data = _minimal()
    data["event"]["end_time"] = data["event"]["start_time"]
    _invalid(data, "end_time must be after start_time")
    data = _minimal()
    data["event"]["end_time"] = "2027-03-13T10:00:01Z"
    _invalid(data, "at most 24 h")


def test_item_must_end_after_start_and_fit_in_event() -> None:
    data = _minimal()
    data["schedule"][0]["end"] = data["schedule"][0]["start"]
    _invalid(data, "end must be after start")
    data = _minimal()
    data["schedule"][0]["end"] = "2027-03-12T18:30:00Z"
    _invalid(data, "outside the event window")


@pytest.mark.parametrize("weight", [-0.1, 1.01, 0.125])
def test_attraction_weight_range_and_precision(weight: float) -> None:
    data = _minimal()
    data["schedule"][0]["attraction_weight"] = weight
    _invalid(data, "attraction_weight")


def test_negative_attendance_and_unknown_category() -> None:
    data = _minimal()
    data["event"]["expected_attendance"] = -1
    _invalid(data, "greater than or equal to 0")
    data = _minimal()
    data["schedule"][0]["category"] = "PARTY"
    _invalid(data, "category")


def test_unknown_key_rejected() -> None:
    data = _minimal()
    data["schedule"][0]["atendance"] = 5
    _invalid(data, "Extra inputs are not permitted")


def test_zone_codes_checked_against_venue() -> None:
    venue = load_venue_config(CONFIGS / "venues" / "v1.yaml")
    EventConfig.model_validate(_minimal()).check_against_venue(venue)
    data = _minimal()
    data["schedule"][0]["zone"] = "ZZ"
    with pytest.raises(ValueError, match=r"\['ZZ'\]"):
        EventConfig.model_validate(data).check_against_venue(venue)


def test_example_v1_event_file() -> None:
    cfg = load_event_config(CONFIGS / "events" / "v1_spring_fest_day1.yaml")
    assert cfg.illustrative is True
    assert cfg.event.venue == "v1"
    cfg.check_against_venue(load_venue_config(CONFIGS / "venues" / "v1.yaml"))
    headline = next(i for i in cfg.schedule if i.title == "Headline band")  # doc 13 §6 record
    assert (headline.zone, headline.expected_attendance, headline.attraction_weight) == (
        "MS",
        2500,
        0.95,
    )
    venue_wide = {i.category for i in cfg.schedule if i.zone is None}
    assert venue_wide == {ScheduleCategory.ENTRY_OPEN, ScheduleCategory.EXIT_WAVE}

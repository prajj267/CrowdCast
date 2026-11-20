"""Event + published schedule YAML format, version 1 (WORKFLOW 2.1.3; spec in doc 12 §6.2).

One file describes one event at one venue and its **published** schedule - the plan announced
before the event. Only the published schedule may be used as forecasting features; the realised
schedule (actual start times, pop-ups) comes from CROWDSIM or from operators and is used for
analysis only (leakage rule, doc 10 §7; doc 12 §5.1 step 7).

Field limits mirror the ``events`` / ``event_schedule_items`` tables (doc 13) and the event API
validation (doc 14 §3.2). Zone codes are checked against the venue with ``check_against_venue``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from crowdcast.common.enums import ScheduleCategory
from crowdcast.common.time import ensure_utc
from crowdcast.venue_graph.config import VenueConfig, ZoneCode

MAX_EVENT_DURATION = timedelta(hours=24)  # doc 14 §3.2


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _to_utc(v: datetime) -> datetime:
    return ensure_utc(v)


class EventInfo(_Strict):
    name: str = Field(min_length=1)
    venue: str = Field(min_length=1)  # venue file stem in configs/venues/, e.g. "v1"
    start_time: AwareDatetime
    end_time: AwareDatetime
    expected_attendance: int | None = Field(None, ge=0)
    is_synthetic: bool = False

    _utc = field_validator("start_time", "end_time")(_to_utc)

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("event end_time must be after start_time")
        if self.end_time - self.start_time > MAX_EVENT_DURATION:
            raise ValueError("event may last at most 24 h")
        return self


class ScheduleItem(_Strict):
    title: str = Field(min_length=1)
    category: ScheduleCategory
    zone: ZoneCode | None = None  # null = venue-wide (e.g. gates open, exit wave)
    start: AwareDatetime
    end: AwareDatetime
    expected_attendance: int | None = Field(None, ge=0)
    attraction_weight: float = Field(0.5, ge=0, le=1)  # DB numeric(3,2)

    _utc = field_validator("start", "end")(_to_utc)

    @field_validator("attraction_weight")
    @classmethod
    def _two_decimals(cls, v: float) -> float:
        if round(v, 2) != v:
            raise ValueError("attraction_weight has at most 2 decimal places")
        return v

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.end <= self.start:
            raise ValueError(f"item {self.title!r}: end must be after start")
        return self


class EventConfig(_Strict):
    format_version: Literal[1]
    illustrative: bool  # true = made-up event (design / simulation / demo)
    event: EventInfo
    schedule: list[ScheduleItem] = Field(default_factory=list)  # the PUBLISHED schedule

    @model_validator(mode="after")
    def _items_inside_event(self) -> Self:
        for item in self.schedule:
            if item.start < self.event.start_time or item.end > self.event.end_time:
                raise ValueError(f"item {item.title!r} lies outside the event window")
        return self

    def check_against_venue(self, venue: VenueConfig) -> None:
        """Raise ``ValueError`` if a schedule item names a zone the venue does not have."""
        known = {z.code for z in venue.zones}
        unknown = sorted({i.zone for i in self.schedule if i.zone is not None} - known)
        if unknown:
            raise ValueError(f"schedule names zones not in venue {venue.venue.name!r}: {unknown}")


def load_event_config(path: Path) -> EventConfig:
    """Parse and validate an event YAML file (zones are checked separately against the venue)."""
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return EventConfig.model_validate(raw)

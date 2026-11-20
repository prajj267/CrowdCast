"""Response and request bodies of the venue/event API (doc 14 §3.2-3.7, as amended in §6)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from crowdcast.common.enums import EventStatus, ScheduleCategory, ZoneType


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VenueOut(_Out):
    venue_id: int
    name: str
    address: str | None
    rho_plan: float | None
    plan_width: int | None
    plan_height: int | None
    floor_plan_path: str | None


class ThresholdsOut(BaseModel):
    elevated: float
    high: float
    critical: float
    source: Literal["DEFAULT", "ZONE"]  # ZONE = at least one per-zone override is stored


class ZoneOut(BaseModel):
    zone_id: int
    code: str
    name: str
    zone_type: ZoneType
    usable_area_m2: float
    planning_capacity: int
    polygon: list[list[float]]
    is_entry: bool
    is_exit: bool
    thresholds: ThresholdsOut
    neighbours: dict[Literal["in", "out"], list[int]]


class ZoneList(BaseModel):
    venue_id: int
    zones: list[ZoneOut]


class ConnectionOut(_Out):
    connection_id: int
    from_zone_id: int | None  # null = outside
    to_zone_id: int | None
    boundary_width_m: float
    travel_time_s: int
    bidirectional: bool


class ConnectionList(BaseModel):
    venue_id: int
    connections: list[ConnectionOut]


class GraphIssueOut(BaseModel):
    code: str
    severity: Literal["ERROR", "WARNING"]
    subject: str
    message: str


class GraphValidation(BaseModel):
    venue_id: int
    valid: bool  # no ERROR issues
    issues: list[GraphIssueOut]


class EventOut(_Out):
    event_id: int
    name: str
    venue_id: int
    start_time: datetime
    end_time: datetime
    expected_attendance: int | None
    status: EventStatus
    is_synthetic: bool


class ActiveModel(BaseModel):
    model_version_id: int
    name: str
    version: str


class EventDetail(EventOut):
    zone_count: int
    camera_count: int
    schedule_item_count: int
    active_model: ActiveModel | None


class EventList(BaseModel):
    events: list[EventOut]
    next_cursor: str | None  # pass as ?cursor= for the next page; null on the last page


class EventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: EventStatus


class ScheduleItemOut(BaseModel):
    item_id: int
    zone_id: int | None  # null = venue-wide
    zone_code: str | None
    title: str
    category: ScheduleCategory
    start_time: datetime
    end_time: datetime
    expected_attendance: int | None
    attraction_weight: float


class Schedule(BaseModel):
    event_id: int
    items: list[ScheduleItemOut]

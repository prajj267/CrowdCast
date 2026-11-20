"""Event read endpoints and status transitions (doc 14 §3.3, §3.4)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.api.schemas import (
    ActiveModel,
    EventDetail,
    EventList,
    EventOut,
    EventPatch,
    Schedule,
    ScheduleItemOut,
)
from crowdcast.common.enums import EventStatus
from crowdcast.storage.interfaces import Event, repository
from crowdcast.venue_graph.interfaces import Severity

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_or_404(session: SessionDep, event_id: int) -> Event:
    event = repository.get_event(session, event_id)
    if event is None:
        raise ApiError(404, "NOT_FOUND", f"event {event_id} not found")
    return event


def _detail(session: SessionDep, event: Event) -> EventDetail:
    counts = repository.event_counts(session, event)
    model = repository.get_model_version(session, event.active_model_version_id)
    return EventDetail(
        **EventOut.model_validate(event).model_dump(),
        zone_count=counts.zone_count,
        camera_count=counts.camera_count,
        schedule_item_count=counts.schedule_item_count,
        active_model=None
        if model is None
        else ActiveModel(
            model_version_id=model.model_version_id, name=model.name, version=model.version
        ),
    )


@router.get("", response_model=EventList)
def list_events(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,  # doc 14 §1
    cursor: Annotated[str | None, Query(pattern=r"^\d+$")] = None,
) -> EventList:
    """Newest first. ``next_cursor`` is opaque to clients: pass it back as ``?cursor=``."""
    events = repository.list_events(
        session, limit=limit + 1, before_id=None if cursor is None else int(cursor)
    )
    has_more = len(events) > limit
    page = events[:limit]
    return EventList(
        events=[EventOut.model_validate(e) for e in page],
        next_cursor=str(page[-1].event_id) if has_more else None,
    )


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: int, session: SessionDep) -> EventDetail:
    return _detail(session, _event_or_404(session, event_id))


@router.patch("/{event_id}", response_model=EventDetail)
def change_status(event_id: int, body: EventPatch, session: SessionDep) -> EventDetail:
    """PLANNED -> LIVE (needs >= 1 zone and a valid graph) and LIVE -> ENDED; else 409."""
    event = _event_or_404(session, event_id)
    if repository.TRANSITIONS.get(event.status) is not body.status:
        raise ApiError(
            409,
            "CONFLICT",
            f"cannot change status from {event.status.value} to {body.status.value}",
        )
    if body.status is EventStatus.LIVE:
        graph = repository.venue_graph(session, event.venue_id)
        errors = [i for i in graph.validate() if i.severity is Severity.ERROR]
        if not graph.zone_codes or errors:
            details = [{"field": i.subject, "issue": f"{i.code}: {i.message}"} for i in errors]
            if not graph.zone_codes:
                details.insert(0, {"field": "venue", "issue": "venue has no zones"})
            raise ApiError(422, "VALIDATION_ERROR", "venue graph is not valid", details)
    repository.set_event_status(session, event, body.status)
    return _detail(session, event)


@router.get("/{event_id}/schedule", response_model=Schedule)
def get_schedule(event_id: int, session: SessionDep) -> Schedule:
    _event_or_404(session, event_id)
    items = [
        ScheduleItemOut(
            item_id=item.item_id,
            zone_id=item.zone_id,
            zone_code=code,
            title=item.title,
            category=item.category,
            start_time=item.start_time,
            end_time=item.end_time,
            expected_attendance=item.expected_attendance,
            attraction_weight=float(item.attraction_weight),
        )
        for item, code in repository.list_schedule(session, event_id)
    ]
    return Schedule(event_id=event_id, items=items)

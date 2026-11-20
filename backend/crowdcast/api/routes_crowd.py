"""The single ingestion endpoint (AD-02; doc 14 §3.8, amended in §6).

The CV pipeline, CROWDSIM replay and annotation import all post here; nothing else writes
observations to the database.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from crowdcast.api.deps import SessionDep
from crowdcast.api.errors import ApiError
from crowdcast.common.time import utc_now
from crowdcast.ingestion.interfaces import (
    BatchRejectedError,
    EventFacts,
    ObservationBatch,
    check_batch,
    check_rows,
)
from crowdcast.storage.interfaces import repository

router = APIRouter(prefix="/api/crowd", tags=["crowd"])


class RejectedOut(BaseModel):
    index: int  # position in the request's observations list
    zone_id: int
    bucket_start: datetime
    reason: str


class IngestResult(BaseModel):
    inserted: int
    updated: int
    rejected: list[RejectedOut]


@router.post("/observations", response_model=IngestResult)
def ingest_observations(batch: ObservationBatch, session: SessionDep) -> IngestResult:
    """Validate a batch, upsert the valid rows, report the rejected ones (HTTP 200)."""
    event = repository.get_event(session, batch.event_id)
    if event is None:
        raise ApiError(404, "NOT_FOUND", f"event {batch.event_id} not found")
    facts = EventFacts(event.status, event.is_synthetic, event.start_time, event.end_time)
    try:
        check_batch(batch, facts)
    except BatchRejectedError as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc

    zone_ids = {z.zone_id for z in repository.list_zones(session, event.venue_id)}
    valid, rejected = check_rows(batch, facts, zone_ids, now=utc_now())
    inserted, updated = repository.upsert_observations(
        session, event.event_id, batch.data_origin, [row.model_dump() for _, row in valid]
    )
    return IngestResult(
        inserted=inserted,
        updated=updated,
        rejected=[RejectedOut(**r.__dict__) for r in rejected],
    )

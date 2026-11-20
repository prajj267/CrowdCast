"""Validation of observation batches for the single ingestion contract (AD-02; doc 14 §3.8).

Pure functions: no database access, the caller passes the event facts and the venue's zone ids.
Batch-level rules raise ``BatchRejectedError``; row-level rules put the row in ``rejected``
so the rest of the batch can still be stored (partial acceptance).

Solo-scope amendments (doc 14 §6): no ADMIN role exists (D7), so SYNTHETIC data is accepted only
for events with ``is_synthetic = true``, and PLANNED/ENDED events accept only SYNTHETIC/MANUAL
back-fill. The "at most 2 min in the future" check applies to REAL data only, because replays of
synthetic or annotated data use event time, which may lie in the future (CLAUDE.md §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from crowdcast.common.enums import DataOrigin, EventStatus, ObsMethod, ObsQuality
from crowdcast.common.time import ensure_utc, is_minute_aligned

MAX_BATCH = 1000
WINDOW_MARGIN = timedelta(minutes=30)
MAX_FUTURE = timedelta(minutes=2)


class ObservationIn(BaseModel):
    """One zone-minute. Signs and alignment are checked per row, not by the schema, so that a
    single bad row does not reject the whole batch."""

    model_config = ConfigDict(extra="forbid")

    zone_id: int
    bucket_start: AwareDatetime
    occupancy: int | None
    occupancy_raw: int | None = None
    inflow: int | None = None
    outflow: int | None = None
    mean_speed_mps: float | None = None
    quality: ObsQuality
    method: ObsMethod


class ObservationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: int
    data_origin: DataOrigin
    source: str | None = Field(None, max_length=64)  # free text, e.g. "cv-worker-1"; not stored
    observations: list[ObservationIn] = Field(min_length=1, max_length=MAX_BATCH)


@dataclass(frozen=True)
class EventFacts:
    status: EventStatus
    is_synthetic: bool
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class RejectedRow:
    index: int
    zone_id: int
    bucket_start: datetime
    reason: str


class BatchRejectedError(Exception):
    """The whole batch is refused. ``status_code`` follows doc 14 §1.1."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def check_batch(batch: ObservationBatch, event: EventFacts) -> None:
    """Rules that apply to every row of the batch at once."""
    origin = batch.data_origin
    if origin is DataOrigin.SYNTHETIC and not event.is_synthetic:
        raise BatchRejectedError(
            422,
            "VALIDATION_ERROR",
            "SYNTHETIC observations are only accepted for events with is_synthetic = true",
        )
    if event.status is not EventStatus.LIVE and origin not in (
        DataOrigin.SYNTHETIC,
        DataOrigin.MANUAL,
    ):
        raise BatchRejectedError(
            409,
            "CONFLICT",
            f"event is {event.status.value}; only SYNTHETIC or MANUAL back-fill is accepted",
        )


def check_rows(
    batch: ObservationBatch, event: EventFacts, venue_zone_ids: set[int], now: datetime
) -> tuple[list[tuple[int, ObservationIn]], list[RejectedRow]]:
    """Split rows into (index, valid row) pairs and rejected rows with reasons."""
    valid: list[tuple[int, ObservationIn]] = []
    rejected: list[RejectedRow] = []
    seen: dict[tuple[int, datetime], int] = {}
    lo, hi = event.start_time - WINDOW_MARGIN, event.end_time + WINDOW_MARGIN
    now = ensure_utc(now)

    for i, row in enumerate(batch.observations):
        t = ensure_utc(row.bucket_start)
        reason = _row_problem(row, t, venue_zone_ids, lo, hi, now, batch.data_origin)
        if reason is None:
            first = seen.get((row.zone_id, t))
            if first is not None:
                reason = f"duplicate of row {first} (same zone and bucket)"
            else:
                seen[(row.zone_id, t)] = i
        if reason is None:
            valid.append((i, row.model_copy(update={"bucket_start": t})))
        else:
            rejected.append(RejectedRow(i, row.zone_id, t, reason))
    return valid, rejected


def _row_problem(
    row: ObservationIn,
    t: datetime,
    venue_zone_ids: set[int],
    lo: datetime,
    hi: datetime,
    now: datetime,
    origin: DataOrigin,
) -> str | None:
    if row.zone_id not in venue_zone_ids:
        return "zone does not belong to the event's venue"
    if not is_minute_aligned(t):
        return "bucket_start is not minute-aligned"
    if not lo <= t <= hi:
        return "bucket_start outside the event window +/- 30 min"
    if origin is DataOrigin.REAL and t > now + MAX_FUTURE:
        return "bucket_start more than 2 min in the future"
    for name in ("occupancy", "occupancy_raw", "inflow", "outflow"):
        value = getattr(row, name)
        if value is not None and value < 0:
            return f"{name} must be >= 0"
    if row.mean_speed_mps is not None and row.mean_speed_mps < 0:
        return "mean_speed_mps must be >= 0"
    if row.occupancy is None and row.quality is not ObsQuality.MISSING:
        return "occupancy may be null only when quality = MISSING"
    return None

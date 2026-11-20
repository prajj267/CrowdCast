"""Time utilities shared by all modules.

Rules (CLAUDE.md §4, DOCUMENTATION/07 §8):
- Every datetime in CROWDCAST is timezone-aware UTC. Naive datetimes are rejected,
  never silently assumed to be UTC, because a wrong guess would shift every bucket.
- Observations are aggregated in 1-minute buckets identified by their start
  (`bucket_start`, minute-aligned: seconds and microseconds are zero).
- Recorded video and simulator replays use *event time*: the configured recording
  start plus the offset into the file. Wall-clock time is never used for them.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

BUCKET = timedelta(minutes=1)


def ensure_utc(dt: datetime) -> datetime:
    """Return `dt` converted to UTC. Raise ValueError for naive datetimes."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"naive datetime not allowed (expected timezone-aware): {dt!r}")
    return dt.astimezone(UTC)


def utc_now() -> datetime:
    """Current wall-clock time in UTC. Use only for live operation, never for replays."""
    return datetime.now(UTC)


def floor_to_minute(dt: datetime) -> datetime:
    """Start of the 1-minute bucket that contains `dt` (in UTC)."""
    return ensure_utc(dt).replace(second=0, microsecond=0)


def is_minute_aligned(dt: datetime) -> bool:
    """True if `dt` is exactly on a minute boundary in UTC."""
    utc = ensure_utc(dt)
    return utc.second == 0 and utc.microsecond == 0


def minute_buckets(start: datetime, end: datetime) -> Iterator[datetime]:
    """Yield bucket starts from floor(start) up to, but excluding, `end`.

    Half-open interval [start, end): a bucket starting exactly at `end` is not included.
    """
    current = floor_to_minute(start)
    stop = ensure_utc(end)
    while current < stop:
        yield current
        current += BUCKET


def event_time(recording_start: datetime, offset_seconds: float) -> datetime:
    """Event time of a moment `offset_seconds` into a recording that began at `recording_start`.

    Used for video frames (offset = frame index / FPS) and simulator ticks.
    """
    if offset_seconds < 0:
        raise ValueError(f"offset must be non-negative, got {offset_seconds}")
    return ensure_utc(recording_start) + timedelta(seconds=offset_seconds)

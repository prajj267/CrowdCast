from datetime import UTC, datetime, timedelta, timezone

import pytest

from crowdcast.common.time import (
    ensure_utc,
    event_time,
    floor_to_minute,
    is_minute_aligned,
    minute_buckets,
)

IST = timezone(timedelta(hours=5, minutes=30))


def test_ensure_utc_rejects_naive() -> None:
    with pytest.raises(ValueError, match="naive"):
        ensure_utc(datetime(2027, 1, 4, 12, 0))


def test_ensure_utc_converts_other_zone() -> None:
    local = datetime(2027, 1, 4, 17, 30, tzinfo=IST)
    assert ensure_utc(local) == datetime(2027, 1, 4, 12, 0, tzinfo=UTC)
    assert ensure_utc(local).tzinfo is UTC


def test_floor_to_minute() -> None:
    dt = datetime(2027, 1, 4, 12, 3, 59, 999_999, tzinfo=UTC)
    assert floor_to_minute(dt) == datetime(2027, 1, 4, 12, 3, tzinfo=UTC)


def test_floor_to_minute_converts_to_utc_first() -> None:
    # 17:33:20 IST is 12:03:20 UTC.
    dt = datetime(2027, 1, 4, 17, 33, 20, tzinfo=IST)
    assert floor_to_minute(dt) == datetime(2027, 1, 4, 12, 3, tzinfo=UTC)


@pytest.mark.parametrize(
    ("dt", "expected"),
    [
        (datetime(2027, 1, 4, 12, 3, tzinfo=UTC), True),
        (datetime(2027, 1, 4, 12, 3, 1, tzinfo=UTC), False),
        (datetime(2027, 1, 4, 12, 3, 0, 1, tzinfo=UTC), False),
    ],
)
def test_is_minute_aligned(dt: datetime, expected: bool) -> None:
    assert is_minute_aligned(dt) is expected


def test_minute_buckets_half_open() -> None:
    start = datetime(2027, 1, 4, 12, 0, 30, tzinfo=UTC)
    end = datetime(2027, 1, 4, 12, 3, tzinfo=UTC)
    assert list(minute_buckets(start, end)) == [
        datetime(2027, 1, 4, 12, 0, tzinfo=UTC),
        datetime(2027, 1, 4, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 4, 12, 2, tzinfo=UTC),
    ]


def test_minute_buckets_empty_when_end_not_after_start() -> None:
    t = datetime(2027, 1, 4, 12, 0, tzinfo=UTC)
    assert list(minute_buckets(t, t)) == []


def test_event_time_from_frame_offset() -> None:
    start = datetime(2027, 1, 4, 12, 0, tzinfo=UTC)
    # Frame 1500 at 25 FPS = 60 s into the recording.
    assert event_time(start, 1500 / 25) == datetime(2027, 1, 4, 12, 1, tzinfo=UTC)


def test_event_time_rejects_negative_offset() -> None:
    with pytest.raises(ValueError):
        event_time(datetime(2027, 1, 4, tzinfo=UTC), -1)

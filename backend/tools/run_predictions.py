"""Drive prediction cycles in EVENT time (WORKFLOW 4.2.1, 4.2.3; doc 10 §12).

Event time comes from the data, never from the wall clock: a cycle is issued at the end of
every bucket that has observations. Two modes:

  back-fill:  every minute the event has data for (or --from/--to), then exit
  --follow:   keep polling; issue one cycle for each newly completed bucket (use while a
              CROWDSIM replay or the CV pipeline is posting observations)

Usage (from backend/):
  uv run python -m tools.run_predictions --event-id 32
  uv run python -m tools.run_predictions --event-id 32 --follow --poll-s 1
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta

from crowdcast.forecasting.interfaces import origin_for, run_cycle
from crowdcast.storage.interfaces import repository, session_scope

ONE_MIN = timedelta(minutes=1)


def latest_issue_time(event_id: int) -> datetime | None:
    """End of the latest bucket with data = the latest issue time that is complete."""
    with session_scope() as s:
        event = repository.get_event(s, event_id)
        if event is None:
            raise SystemExit(f"event {event_id} not found")
        _, last = repository.observation_bucket_range(s, event_id, origin_for(event.is_synthetic))
    return None if last is None else last + ONE_MIN


def first_issue_time(event_id: int) -> datetime | None:
    with session_scope() as s:
        event = repository.get_event(s, event_id)
        assert event is not None
        first, _ = repository.observation_bucket_range(s, event_id, origin_for(event.is_synthetic))
    return None if first is None else first + ONE_MIN


def run_range(event_id: int, start: datetime, end: datetime) -> int:
    """Cycles for issue times start..end inclusive, one transaction each."""
    written = 0
    t = start
    while t <= end:
        with session_scope() as s:
            written += run_cycle(s, event_id, t).written
        t += ONE_MIN
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", type=int, required=True)
    parser.add_argument("--from", dest="start", type=datetime.fromisoformat, default=None)
    parser.add_argument("--to", dest="end", type=datetime.fromisoformat, default=None)
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--poll-s", type=float, default=2.0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)

    start = args.start or first_issue_time(args.event_id)
    end = args.end or latest_issue_time(args.event_id)
    if start is None or end is None:
        if not args.follow:
            print("no observations for this event yet")
            return 0
    else:
        t0 = time.perf_counter()
        n = run_range(args.event_id, start, end)
        print(
            f"cycles {start.isoformat()} .. {end.isoformat()}: {n} predictions "
            f"in {time.perf_counter() - t0:.1f} s"
        )
    if not args.follow:
        return 0

    done = end
    print("following; Ctrl+C to stop")
    try:
        while True:
            latest = latest_issue_time(args.event_id)
            if latest is not None and (done is None or latest > done):
                first = latest if done is None else done + ONE_MIN
                n = run_range(args.event_id, first, latest)
                print(f"issued up to {latest.isoformat()} (+{n} predictions)")
                done = latest
            time.sleep(args.poll_s)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())

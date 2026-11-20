# 05 — Time handling

Code: `backend/crowdcast/common/time.py`. Time bugs are among the most common and hardest to see,
and in forecasting a time bug can silently become *data leakage*, so we are strict.

## UTC everywhere

- **UTC** is a single global clock with no daylight-saving jumps.
- A **naive** datetime (`2026-11-20 14:00`) has no time zone — nobody knows which 14:00 it is.
  An **aware** datetime carries its offset (`14:00+00:00`).
- Rule: store and compute in UTC; convert to local time only for display. `ensure_utc()` raises
  an error on naive datetimes, and the ruff rule `DTZ` forbids creating them. Postgres columns are
  `timestamptz`, and every connection uses `TimeZone=UTC`.

## Minute buckets

Observations are aggregated per minute. A **bucket** is the half-open interval
`[t, t + 1 min)`: 14:03:00 belongs to bucket 14:03, 14:03:59.9 too, 14:04:00 to the next.
`floor_to_minute()` maps a timestamp to its bucket; the database rejects any `bucket_start` that
is not on a whole minute. Half-open intervals mean every instant belongs to exactly one bucket.

## Event time vs wall-clock time

We process *recorded* video and *replay* simulations. If timestamps came from the computer clock
("now"), a replay run today and tomorrow would produce different data, and processing speed would
change the timeline. Instead:

```
event_time = configured event start + offset into the recording
```

`event_time(recording_start, offset_seconds)` does this. A frame 125 s into a video whose
recording started at 18:00:00 UTC belongs to 18:02:05 → bucket 18:02, regardless of when or how
fast we process it. This makes every run reproducible.

## Viva questions

- **Why not store local time?** Daylight-saving changes make local time repeat or skip an hour;
  sorting and differences become wrong.
- **Why half-open buckets?** So boundaries are unambiguous: no instant is in two buckets or none.
- **How could time handling cause leakage?** If a feature for minute t accidentally used data
  timestamped later than t (e.g. a window closed on the wrong side), the model would "see the
  future" during training. Right-closed windows on aligned buckets prevent that (doc 10 §7).

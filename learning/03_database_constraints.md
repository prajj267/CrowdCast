# 03 — Database design and constraints

The full schema is in `DOCUMENTATION/13_DATABASE_DESIGN.md`; the code is
`backend/crowdcast/storage/models.py`. This note explains the *ideas*.

## Keys

- **Primary key (PK):** the unique ID of a row, e.g. `zone_id`. We use auto-generated integers.
- **Foreign key (FK):** a column that must point at an existing row in another table, e.g.
  `zones.venue_id → venues.venue_id`. The database refuses a zone for a venue that doesn't exist.
- `ON DELETE SET NULL` / `CASCADE` say what happens to referring rows when the target is deleted.

## Constraints: the database as the last line of defence

Application code has bugs. If the *database* refuses invalid rows, a bug cannot silently corrupt
the data that every result is computed from. Examples from our schema:

| Constraint type | Example | What it prevents |
|---|---|---|
| `CHECK` | `bucket_start = date_trunc('minute', bucket_start)` | Observations not aligned to a minute |
| `CHECK` | `p10 <= p50 <= p90` on predictions | "Quantile crossing" — a lower bound above the median |
| `CHECK` | `horizon_min IN (5, 15, 30)` | Forecasts for horizons the system doesn't support |
| `UNIQUE` | `(event_id, zone_id, bucket_start, data_origin)` | Two observations for the same zone and minute from the same source |
| Partial unique index | one *unresolved* alert per zone and type | Duplicate open alerts (resolved ones may repeat) |
| Partial unique index | only one `model_versions` row with `is_active = true` | Two models being "the active one" |
| `NULLS NOT DISTINCT` | on zone connections, where `NULL` means "outside the venue" | Two identical "outside → zone A" connections (normally NULLs never count as equal) |

`tests/test_storage_schema.py` proves each rule by inserting a bad row and expecting rejection.

## Enums

A column that may only hold listed values (e.g. `data_origin` ∈ `REAL`, `MANUAL`, `SYNTHETIC`).
We store the readable *value*, defined once in `crowdcast/common/enums.py`.

`data_origin` matters for research integrity: synthetic and real data are never mixed by
accident, because every observation carries its origin and it is part of the unique key.

## Indexes

An index is like a book index: it lets the database find rows without scanning the whole table.
`(event_id, bucket_start DESC)` serves the most common query ("latest observations for this
event"). A **BRIN** index on `bucket_start` is tiny and works well because rows arrive in time
order.

## Viva questions

- **Why enforce rules in the database and not only in Python?** Because the API, replay tool and
  scripts all write data; one rule in one place catches mistakes from any of them.
- **Why is `data_origin` in the unique key?** The same zone-minute can legitimately have a
  synthetic and a manual value; they must stay separate rows, not overwrite each other.

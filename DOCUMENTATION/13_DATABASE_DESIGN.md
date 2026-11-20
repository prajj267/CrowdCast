# 13 — Database Design

| Field | Value |
|---|---|
| Version | 0.2 (solo scope; changes listed in §8) |
| DBMS | PostgreSQL 16 |
| Migrations | Alembic (`backend/crowdcast/storage/migrations`); ORM models in `backend/crowdcast/storage/models.py` |
| ER diagram | [ARCHITECTURE/database_er.mmd](../ARCHITECTURE/database_er.mmd) |

---

## 1. Design principles

1. **Configuration is relational; measurements are append-mostly time series** in the same database (AD-05).
2. **Only aggregates are stored.** There is no table for tracks, detections, faces or images (NFR-PRV-02).
3. **Every measurement carries its provenance** (`data_origin`, `method`, `quality`).
4. All timestamps are `timestamptz` in UTC; buckets are aligned to the minute.
5. Surrogate `bigint` identity keys; human-readable `code` columns where users type identifiers.

## 2. Enumerated types

```sql
-- user_role removed in v0.2 (no authentication, decision D7)
CREATE TYPE event_status     AS ENUM ('PLANNED','LIVE','ENDED');
CREATE TYPE zone_type        AS ENUM ('STAGE','CORRIDOR','FOOD','ENTRY','EXIT','ENTRY_EXIT',
                                      'SEATING','EXHIBITION','FACILITY','OPEN_AREA','OTHER');
CREATE TYPE schedule_category AS ENUM ('PERFORMANCE','MEAL','ENTRY_OPEN','EXIT_WAVE','ANNOUNCEMENT','OTHER');
CREATE TYPE data_origin      AS ENUM ('REAL','MANUAL','SYNTHETIC');
CREATE TYPE obs_method       AS ENUM ('DETECTION','DENSITY_MAP','FUSED','MANUAL','SIM_CLEAN','SIM_NOISY');
CREATE TYPE obs_quality      AS ENUM ('OK','LOW_CONFIDENCE','PARTIAL','MISSING');
CREATE TYPE congestion_level AS ENUM ('NORMAL','ELEVATED','HIGH','CRITICAL');
CREATE TYPE alert_type       AS ENUM ('CURRENT','PREDICTED');
CREATE TYPE alert_status     AS ENUM ('OPEN','ACKNOWLEDGED','RESOLVED');
CREATE TYPE camera_kind      AS ENUM ('FILE','RTSP');
```

## 3. Tables

### 3.1 `users` — removed in v0.2

Not created: the solo prototype has no authentication (decision D7). All foreign keys to `users` are removed as well (§8).

### 3.2 `venues`

| Column | Type | Constraints |
|---|---|---|
| venue_id | bigint identity | **PK** |
| name | text | NOT NULL |
| address | text | NULL |
| floor_plan_path | text | NULL (file in object storage folder) |
| plan_width, plan_height | integer | Plan coordinate system size |
| rho_plan | numeric(4,2) | NULL; persons/m² default for capacity derivation; organiser-entered |
| created_at | timestamptz | NOT NULL DEFAULT now() |

### 3.3 `zones`

| Column | Type | Constraints |
|---|---|---|
| zone_id | bigint identity | **PK** |
| venue_id | bigint | **FK → venues** ON DELETE CASCADE |
| code | varchar(16) | NOT NULL; UNIQUE (venue_id, code) |
| name | text | NOT NULL |
| zone_type | zone_type | NOT NULL |
| usable_area_m2 | numeric(10,2) | NOT NULL, CHECK > 0 |
| planning_capacity | integer | NOT NULL, CHECK > 0 |
| polygon | jsonb | NOT NULL — `[[x,y],...]` in plan coordinates |
| is_entry | boolean | NOT NULL DEFAULT false |
| is_exit | boolean | NOT NULL DEFAULT false |
| threshold_elevated | numeric(4,3) | NULL (default 0.600) |
| threshold_high | numeric(4,3) | NULL (default 0.800) |
| threshold_critical | numeric(4,3) | NULL (default 0.950); CHECK elevated < high < critical, where an unset threshold takes its default (`COALESCE(threshold_x, default)`) |

### 3.4 `zone_connections`

| Column | Type | Constraints |
|---|---|---|
| connection_id | bigint identity | **PK** |
| venue_id | bigint | **FK → venues** |
| from_zone_id | bigint | **FK → zones**; NULL means "outside" ($\omega$) |
| to_zone_id | bigint | **FK → zones**; NULL means "outside" |
| boundary_width_m | numeric(6,2) | NOT NULL, CHECK > 0 |
| travel_time_s | integer | NOT NULL, CHECK > 0 |
| bidirectional | boolean | NOT NULL DEFAULT true |
| | | CHECK (from_zone_id IS DISTINCT FROM to_zone_id); CHECK not both NULL; UNIQUE NULLS NOT DISTINCT (venue_id, from_zone_id, to_zone_id), so a connection to "outside" cannot be duplicated |

### 3.5 `events`

| Column | Type | Constraints |
|---|---|---|
| event_id | bigint identity | **PK** |
| venue_id | bigint | **FK → venues** |
| name | text | NOT NULL |
| start_time, end_time | timestamptz | NOT NULL; CHECK end_time > start_time |
| expected_attendance | integer | NULL, CHECK ≥ 0 |
| status | event_status | NOT NULL DEFAULT 'PLANNED' |
| is_synthetic | boolean | NOT NULL DEFAULT false |
| active_model_version_id | bigint | **FK → model_versions**, NULL (falls back to global active) |

### 3.6 `event_operators` — removed in v0.2

Not created (no users, decision D7).

### 3.7 `event_schedule_items`

| Column | Type | Constraints |
|---|---|---|
| item_id | bigint identity | **PK** |
| event_id | bigint | **FK → events** ON DELETE CASCADE |
| zone_id | bigint | **FK → zones**, NULL = venue-wide |
| title | text | NOT NULL |
| category | schedule_category | NOT NULL |
| start_time, end_time | timestamptz | NOT NULL; CHECK end > start |
| expected_attendance | integer | NULL |
| attraction_weight | numeric(3,2) | NOT NULL DEFAULT 0.5, CHECK 0 ≤ w ≤ 1 |
| updated_at | timestamptz | NOT NULL — features read the version valid at issue time |

### 3.8 `camera_sources`

| Column | Type | Constraints |
|---|---|---|
| camera_id | bigint identity | **PK** |
| venue_id | bigint | **FK → venues** |
| name | text | NOT NULL |
| kind | camera_kind | NOT NULL |
| uri | text | NOT NULL — local video file path (v0.2: replaces Fernet-encrypted `uri_encrypted`; no live camera URLs or credentials, decision D6) |
| target_fps | smallint | NOT NULL DEFAULT 5 |
| image_size | smallint | NOT NULL DEFAULT 640 |
| homography | jsonb | NULL — 3×3 matrix image→metres |
| is_enabled | boolean | NOT NULL DEFAULT true |

### 3.9 `camera_zone_regions`

| Column | Type | Constraints |
|---|---|---|
| region_id | bigint identity | **PK** |
| camera_id | bigint | **FK → camera_sources** |
| zone_id | bigint | **FK → zones** |
| polygon_px | jsonb | NOT NULL |
| coverage_fraction | numeric(4,3) | NOT NULL DEFAULT 1, CHECK 0 < c ≤ 1 |
| is_primary | boolean | NOT NULL |
| | | Partial UNIQUE (zone_id) WHERE is_primary — one primary camera per zone |

### 3.10 `counting_lines`

| Column | Type | Constraints |
|---|---|---|
| line_id | bigint identity | **PK** |
| camera_id | bigint | **FK → camera_sources** |
| connection_id | bigint | **FK → zone_connections**; **UNIQUE** (one line per connection — no double counting) |
| p1, p2 | jsonb | `[x,y]` image pixels |
| positive_side_zone_id | bigint | **FK → zones** (or NULL = outside); crossing toward this side counts as entering it |

### 3.11 `crowd_observations` (time series)

| Column | Type | Constraints |
|---|---|---|
| observation_id | bigint identity | **PK** |
| event_id | bigint | **FK → events** |
| zone_id | bigint | **FK → zones** |
| bucket_start | timestamptz | NOT NULL; CHECK date_trunc('minute', bucket_start) = bucket_start |
| occupancy | integer | NULL when quality = MISSING; CHECK ≥ 0 |
| occupancy_raw | integer | NULL |
| inflow | integer | NULL, CHECK ≥ 0 |
| outflow | integer | NULL, CHECK ≥ 0 |
| mean_speed_mps | real | NULL |
| quality | obs_quality | NOT NULL |
| method | obs_method | NOT NULL |
| data_origin | data_origin | NOT NULL |
| ingested_at | timestamptz | NOT NULL DEFAULT now() |
| | | **UNIQUE (event_id, zone_id, bucket_start, data_origin)** — upsert key |

### 3.12 `model_versions`

| Column | Type | Constraints |
|---|---|---|
| model_version_id | bigint identity | **PK** |
| name | text | e.g. `xgb_A4` |
| version | text | e.g. `v3`; UNIQUE (name, version) |
| model_family | text | `PERSISTENCE`, `XGBOOST`, `LSTM`, `GNN` |
| feature_set | text | `A1`…`A5` |
| artifact_path | text | NOT NULL |
| trained_on | jsonb | Event IDs/hash, data origins |
| metrics | jsonb | Validation metrics |
| is_active | boolean | Partial UNIQUE WHERE is_active (one global active) |
| created_at | timestamptz | NOT NULL |

### 3.13 `predictions`

| Column | Type | Constraints |
|---|---|---|
| prediction_id | bigint identity | **PK** |
| event_id | bigint | **FK → events** |
| zone_id | bigint | **FK → zones** |
| issued_at | timestamptz | NOT NULL (bucket $t$) |
| horizon_min | smallint | NOT NULL, CHECK IN (5, 15, 30) |
| target_time | timestamptz | NOT NULL = issued_at + horizon |
| p10, p50, p90 | real | NOT NULL; CHECK p10 ≤ p50 ≤ p90; CHECK p10 ≥ 0 |
| predicted_level | congestion_level | NOT NULL (from p50) |
| risk_score | real | CHECK 0 ≤ r ≤ 1 |
| model_version_id | bigint | **FK → model_versions** |
| is_fallback | boolean | NOT NULL DEFAULT false |
| | | UNIQUE (event_id, zone_id, issued_at, horizon_min, model_version_id) |

### 3.14 `congestion_alerts`

| Column | Type | Constraints |
|---|---|---|
| alert_id | bigint identity | **PK** |
| event_id | bigint | **FK → events** |
| zone_id | bigint | **FK → zones** |
| alert_type | alert_type | NOT NULL |
| level | congestion_level | NOT NULL (current severity, may escalate) |
| horizon_min | smallint | NULL for CURRENT |
| predicted_onset | timestamptz | NULL for CURRENT |
| trigger_value | real | $u$ or $\hat u^{50}$ that triggered |
| status | alert_status | NOT NULL DEFAULT 'OPEN' |
| message | text | NOT NULL |
| opened_at | timestamptz | NOT NULL |
| acknowledged_at | timestamptz | NULL |
| resolved_at | timestamptz | NULL |
| auto_resolved | boolean | NOT NULL DEFAULT false (v0.2: replaces `resolved_by`, where NULL meant "auto") |
| prediction_id | bigint | **FK → predictions** ON DELETE SET NULL, NULL |
| | | Partial UNIQUE (event_id, zone_id, alert_type) WHERE status <> 'RESOLVED' (FR-ALR-04); CHECK `horizon_min` and `predicted_onset` are NULL for CURRENT and NOT NULL for PREDICTED |

### 3.15 `audit_log`

| Column | Type | Constraints |
|---|---|---|
| audit_id | bigint identity | **PK** |
| actor | text | NOT NULL, CHECK IN ('USER','SYSTEM') (v0.2: replaces `user_id`) |
| action | text | e.g. `ALERT_ACK`, `MODEL_ACTIVATE`, `CAMERA_CREATE` |
| entity, entity_id | text, bigint | |
| details | jsonb | |
| created_at | timestamptz | NOT NULL |

## 4. Relationships (summary)

- venue 1—N zones, zone_connections, camera_sources, events
- event 1—N schedule items, observations, predictions, alerts
- zone 1—N observations, predictions, alerts, camera_zone_regions
- zone_connection 1—0..1 counting_line
- camera 1—N regions, counting_lines
- model_version 1—N predictions
- prediction 1—0..1 alert

## 5. Indexing recommendations

| Index | Supports |
|---|---|
| `crowd_observations (event_id, zone_id, bucket_start DESC)` (the unique key covers this order if declared accordingly) | Feature windows, zone history charts |
| `crowd_observations (event_id, bucket_start DESC)` | "Current state of all zones" |
| BRIN on `crowd_observations (bucket_start)` | Cheap range scans for retention/export |
| `predictions (event_id, issued_at DESC)` | Latest cycle |
| `predictions (event_id, zone_id, horizon_min, target_time)` | Predicted-vs-actual charts |
| `congestion_alerts (event_id, status, opened_at DESC)` | Alerts page |
| `event_schedule_items (event_id, start_time)` | Schedule features |
| `zones (venue_id)`, `zone_connections (venue_id)` | Graph loading |

Volume check: 100 events × 15 zones × 720 min ≈ 1.1 M observations and 3.2 M predictions (3 horizons) — comfortably within plain PostgreSQL on a laptop (NFR-SCL-02). If needed, `crowd_observations` and `predictions` can be range-partitioned by `bucket_start`/`issued_at` month, or TimescaleDB hypertables enabled.

## 6. Example records

```sql
INSERT INTO venues (name, address, rho_plan, plan_width, plan_height)
VALUES ('North Campus Grounds', 'Example University', 1.50, 1200, 800);

INSERT INTO zones (venue_id, code, name, zone_type, usable_area_m2, planning_capacity, polygon, is_entry, is_exit)
VALUES (1, 'MS', 'Main Stage', 'STAGE', 2000, 3000, '[[600,100],[1100,100],[1100,450],[600,450]]', false, false),
       (1, 'C1', 'Central Corridor', 'CORRIDOR', 400, 500, '[[400,300],[600,300],[600,380],[400,380]]', false, false);

INSERT INTO zone_connections (venue_id, from_zone_id, to_zone_id, boundary_width_m, travel_time_s, bidirectional)
VALUES (1, 2, 1, 8.0, 45, true);

INSERT INTO events (venue_id, name, start_time, end_time, expected_attendance, status)
VALUES (1, 'Spring Fest 2027 – Day 1', '2027-03-12 10:30:00+00', '2027-03-12 17:30:00+00', 5000, 'PLANNED');

INSERT INTO event_schedule_items (event_id, zone_id, title, category, start_time, end_time, expected_attendance, attraction_weight, updated_at)
VALUES (1, 1, 'Headline band', 'PERFORMANCE', '2027-03-12 14:00+00', '2027-03-12 15:00+00', 2500, 0.95, now());

INSERT INTO crowd_observations (event_id, zone_id, bucket_start, occupancy, occupancy_raw, inflow, outflow,
                                mean_speed_mps, quality, method, data_origin)
VALUES (1, 2, '2027-03-12 13:52:00+00', 312, 287, 64, 41, 0.9, 'OK', 'DETECTION', 'REAL');

INSERT INTO predictions (event_id, zone_id, issued_at, horizon_min, target_time, p10, p50, p90,
                         predicted_level, risk_score, model_version_id, is_fallback)
VALUES (1, 2, '2027-03-12 13:52:00+00', 15, '2027-03-12 14:07:00+00', 360, 418, 470, 'HIGH', 0.76, 4, false);
```

(Dates and values are illustrative examples, not data.)

## 7. Retention

| Data | Retention | Mechanism |
|---|---|---|
| Observations, predictions, alerts | 12 months (configurable) | Nightly job deletes by `event.end_time` |
| Audit log | 12 months | Same |
| Raw video (outside DB) | ≤ 30 days unless consented research use | File retention job ([19](19_SECURITY_AND_PRIVACY.md)) |

## 8. Change log

| Version | Date | Change | Reason |
|---|---|---|---|
| 0.2 | 2026-11-20 | Removed `users`, `event_operators`, the `user_role` enum and every user foreign key (`venues.created_by`, `events.created_by`, `congestion_alerts.acknowledged_by` / `resolved_by`, `audit_log.user_id`) | D7: no authentication in the solo prototype |
| 0.2 | 2026-11-20 | `congestion_alerts.auto_resolved` (boolean) replaces `resolved_by`; `audit_log.actor` ('USER' / 'SYSTEM') replaces `user_id` | Keeps the information those columns carried without users |
| 0.2 | 2026-11-20 | `camera_sources.uri` (text, local file path) replaces `uri_encrypted` (bytea, Fernet) | D6: recorded public-dataset files only, no camera credentials to protect |
| 0.2 | 2026-11-20 | Made explicit: NULLS NOT DISTINCT on the `zone_connections` key; COALESCE-to-default in the threshold-order CHECK; CHECK tying `horizon_min` / `predicted_onset` to `alert_type`; `prediction_id` ON DELETE SET NULL | Close gaps in v0.1 that would have let invalid rows in |

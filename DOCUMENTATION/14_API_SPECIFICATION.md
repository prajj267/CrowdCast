# 14 — API Specification

| Field | Value |
|---|---|
| Version | 0.2 (implementation amendments in §6) |
| Style | REST over HTTPS, JSON, FastAPI (OpenAPI 3.1 generated at `/api/docs`) |
| Base path | `/api` |
| Auth | **None** in the solo scope (decision D7, WORKFLOW.md): no tokens, roles or users; role columns in §2 do not apply |

---

## 1. Conventions

- Timestamps: ISO 8601 UTC (`2027-03-12T13:52:00Z`). Observation buckets must be minute-aligned.
- IDs: integers. Zone `code` accepted where noted.
- Pagination: `?limit=` (default 50, max 500) and `?cursor=`; responses include `next_cursor`.
- All request bodies are validated by Pydantic; unknown fields rejected (`extra="forbid"`).

### 1.1 Error envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "end_time must be after start_time",
    "details": [{ "field": "end_time", "issue": "must be > start_time" }],
    "request_id": "c1f9e1b2-6a7d-4d7e-9e0c-2b8f8c1a0f11"
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `BAD_REQUEST` | Malformed JSON |
| 401 | `UNAUTHENTICATED` | Missing/invalid/expired token |
| 403 | `FORBIDDEN` | Role or event assignment insufficient |
| 404 | `NOT_FOUND` | Resource missing or not visible to caller |
| 409 | `CONFLICT` | Duplicate, invalid state transition |
| 422 | `VALIDATION_ERROR` | Schema/semantic validation failed |
| 429 | `RATE_LIMITED` | Login throttling |
| 500 | `INTERNAL_ERROR` | Unexpected; details logged, not returned |

### 1.2 Role legend

`A` = ADMIN, `O` = ORGANISER, `P` = OPERATOR (assigned events only), `S` = SERVICE.

## 2. Endpoint summary

| Method | URL | Purpose | Roles | Req. |
|---|---|---|---|---|
| POST | `/api/auth/login` | Obtain tokens | public | FR-AUTH-01 |
| POST | `/api/auth/refresh` | Refresh access token | any user | FR-AUTH-01 |
| GET | `/api/auth/me` | Current user | any user | — |
| GET/POST | `/api/users` | List/create users | A | FR-AUTH-03 |
| PATCH | `/api/users/{user_id}` | Update role/active | A | FR-AUTH-03 |
| POST | `/api/venues` | Create venue | A, O | FR-VEN-01 |
| GET | `/api/venues/{venue_id}` | Venue detail | A, O, P | — |
| GET | `/api/venues/{venue_id}/zones` | List zones | A, O, P | FR-ZON-01 |
| POST | `/api/venues/{venue_id}/zones` | Create zone | A, O | FR-ZON-01/02 |
| PATCH/DELETE | `/api/zones/{zone_id}` | Update/delete zone | A, O | FR-ZON-01/06 |
| GET/POST | `/api/venues/{venue_id}/connections` | List/create connections | A, O (GET also P) | FR-ZON-03 |
| GET | `/api/venues/{venue_id}/graph/validate` | Validate graph | A, O | FR-ZON-05 |
| POST | `/api/events` | Create event | A, O | FR-EVT-01 |
| GET | `/api/events` | List visible events | A, O, P | — |
| GET | `/api/events/{event_id}` | Event detail | A, O, P | — |
| PATCH | `/api/events/{event_id}` | Update / status transition | A, O | FR-EVT-02 |
| GET/POST | `/api/events/{event_id}/schedule` | List/add schedule items | GET: A, O, P; POST: A, O | FR-EVT-03 |
| PATCH/DELETE | `/api/schedule-items/{item_id}` | Edit/delete item | A, O | FR-EVT-04 |
| PUT | `/api/events/{event_id}/operators` | Assign operators | A, O | FR-EVT-05 |
| POST | `/api/cameras` | Register camera | A | FR-VID-01 |
| GET | `/api/cameras/{camera_id}/config` | Geometry for CV worker | A, S | FR-VID-03 |
| PUT | `/api/cameras/{camera_id}/regions` | Set regions | A | FR-VID-03 |
| PUT | `/api/cameras/{camera_id}/lines` | Set counting lines | A | FR-VID-03 |
| POST | `/api/crowd/observations` | Ingest observation batch | S, A | FR-OBS-01…03 |
| POST | `/api/crowd/observations/import` | CSV import (manual) | A, O | FR-OBS-05 |
| GET | `/api/crowd/current/{event_id}` | Latest state of all zones | A, O, P | FR-DSH-04 |
| GET | `/api/crowd/history/{event_id}` | Time series | A, O, P | FR-DSH-06 |
| GET | `/api/predictions/{event_id}` | Latest predictions | A, O, P | FR-FC-01 |
| GET | `/api/predictions/{event_id}/zones/{zone_id}` | Forecast timeline incl. past predictions | A, O, P | FR-DSH-05/06 |
| GET | `/api/alerts/{event_id}` | List alerts | A, O, P | FR-ALR-* |
| POST | `/api/alerts/{alert_id}/acknowledge` | Acknowledge | A, O, P | FR-ALR-02 |
| POST | `/api/alerts/{alert_id}/resolve` | Resolve | A, O, P | FR-ALR-02 |
| GET | `/api/models` | List model versions | A, O | FR-FC-05 |
| POST | `/api/models/{model_version_id}/activate` | Activate | A | FR-FC-05 |
| GET | `/api/health` | Liveness + DB + last cycle time | public (minimal) | NFR-REL |

## 3. Detailed specifications

### 3.1 `POST /api/auth/login`

Request:
```json
{ "email": "operator1@example.edu", "password": "••••••••" }
```
Response 200:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { "user_id": 7, "full_name": "Operator One", "role": "OPERATOR" }
}
```
The refresh token is set as an `HttpOnly; Secure; SameSite=Strict` cookie (7-day lifetime).
Validation: email format; password 1–128 chars. Errors: 401 (wrong credentials — generic message), 429 (≥ 5 failures in 10 min for that email/IP).

### 3.2 `POST /api/events`

Request:
```json
{
  "name": "Spring Fest 2027 – Day 1",
  "venue_id": 1,
  "start_time": "2027-03-12T10:30:00Z",
  "end_time": "2027-03-12T17:30:00Z",
  "expected_attendance": 5000,
  "is_synthetic": false
}
```
Response 201:
```json
{
  "event_id": 12,
  "name": "Spring Fest 2027 – Day 1",
  "venue_id": 1,
  "start_time": "2027-03-12T10:30:00Z",
  "end_time": "2027-03-12T17:30:00Z",
  "expected_attendance": 5000,
  "status": "PLANNED",
  "is_synthetic": false,
  "created_by": 2
}
```
Validation: venue exists; `end_time > start_time`; duration ≤ 24 h; `expected_attendance ≥ 0`. Errors: 404 venue, 422.

### 3.3 `GET /api/events/{event_id}`

Response 200: event object (as above) plus
```json
{ "zone_count": 8, "camera_count": 3, "schedule_item_count": 14,
  "active_model": { "model_version_id": 4, "name": "xgb_A4", "version": "v3" } }
```
Errors: 404 (also returned to an OPERATOR not assigned to the event, to avoid leaking existence).

### 3.4 `PATCH /api/events/{event_id}` — status transition

```json
{ "status": "LIVE" }
```
Allowed: `PLANNED→LIVE`, `LIVE→ENDED`. Otherwise 409 `CONFLICT`. Going LIVE requires ≥ 1 zone and a valid graph (else 422 with graph issues).

### 3.5 `POST /api/venues`

```json
{ "name": "North Campus Grounds", "address": "Example University", "rho_plan": 1.5,
  "plan_width": 1200, "plan_height": 800 }
```
Response 201 with `venue_id`. Floor plan uploaded separately via `PUT /api/venues/{venue_id}/floor-plan` (multipart, ≤ 5 MB, PNG/JPEG/SVG; SVG sanitised).

### 3.6 `GET /api/venues/{venue_id}/zones`

Response 200:
```json
{
  "venue_id": 1,
  "zones": [
    {
      "zone_id": 1, "code": "MS", "name": "Main Stage", "zone_type": "STAGE",
      "usable_area_m2": 2000.0, "planning_capacity": 3000,
      "polygon": [[600,100],[1100,100],[1100,450],[600,450]],
      "is_entry": false, "is_exit": false,
      "thresholds": { "elevated": 0.6, "high": 0.8, "critical": 0.95, "source": "DEFAULT" },
      "neighbours": { "in": [2, 6], "out": [2, 6] }
    }
  ]
}
```

### 3.7 `POST /api/venues/{venue_id}/zones`

```json
{ "code": "FC", "name": "Food Court", "zone_type": "FOOD", "usable_area_m2": 800,
  "planning_capacity": null, "polygon": [[200,450],[450,450],[450,700],[200,700]] }
```
If `planning_capacity` is null and venue `rho_plan` is set, server computes $\lfloor A \cdot \rho_{plan}\rfloor$; if both null → 422. Validation: code `^[A-Z0-9_]{1,16}$` unique per venue (409); polygon 3–100 vertices within plan bounds, non-self-intersecting (Shapely `is_valid`).

### 3.8 `POST /api/crowd/observations` (ingestion contract — AD-02)

Request:
```json
{
  "event_id": 12,
  "data_origin": "REAL",
  "source": "cv-worker-1",
  "observations": [
    {
      "zone_id": 2,
      "bucket_start": "2027-03-12T13:52:00Z",
      "occupancy": 312,
      "occupancy_raw": 287,
      "inflow": 64,
      "outflow": 41,
      "mean_speed_mps": 0.9,
      "quality": "OK",
      "method": "DETECTION"
    }
  ]
}
```
Response 200:
```json
{ "inserted": 1, "updated": 0, "rejected": [] }
```
Validation:
- Event exists and is `LIVE` (or `PLANNED/ENDED` only for `SYNTHETIC`/`MANUAL` back-fill by ADMIN).
- Each zone belongs to the event's venue.
- `bucket_start` minute-aligned, within `[start_time − 30 min, end_time + 30 min]`, not more than 2 min in the future.
- Non-negative integers; `occupancy` may be null only if `quality = MISSING`.
- `data_origin = SYNTHETIC` only allowed when the event has `is_synthetic = true` **or** the caller is ADMIN (prevents mixing synthetic data into real events by accident).
- Batch ≤ 1,000 rows.
- Partial acceptance: invalid rows returned in `rejected` with reasons; valid rows upserted (HTTP 200). Whole-batch structural errors → 422.

### 3.9 `GET /api/crowd/current/{event_id}`

Response 200:
```json
{
  "event_id": 12,
  "as_of": "2027-03-12T13:52:00Z",
  "zones": [
    {
      "zone_id": 2, "code": "C1", "name": "Central Corridor",
      "occupancy": 312, "capacity": 500, "occupancy_ratio": 0.624,
      "density_ppm2": 0.78, "inflow": 64, "outflow": 41, "mean_speed_mps": 0.9,
      "level": "ELEVATED", "quality": "OK", "data_origin": "REAL",
      "staleness_s": 14
    }
  ]
}
```
`staleness_s` lets the UI grey out zones whose latest data is older than 3 minutes.

### 3.10 `GET /api/crowd/history/{event_id}`

Query: `zone_id` (optional, repeatable), `from`, `to`, `origin` (default: `REAL` then `MANUAL` then `SYNTHETIC` precedence), `resolution` (`1m`, `5m`).
Response: `{ "series": [ { "zone_id": 2, "points": [ { "t": "...", "occupancy": 300, "inflow": 60, "outflow": 45 } ] } ] }`.
Validation: range ≤ 24 h; `from < to`.

### 3.11 `GET /api/predictions/{event_id}`

Response 200 (latest cycle):
```json
{
  "event_id": 12,
  "issued_at": "2027-03-12T13:52:00Z",
  "model": { "model_version_id": 4, "name": "xgb_A4", "version": "v3" },
  "zones": [
    {
      "zone_id": 2, "code": "C1",
      "current": { "occupancy": 312, "occupancy_ratio": 0.624, "level": "ELEVATED" },
      "forecasts": [
        { "horizon_min": 5,  "target_time": "2027-03-12T13:57:00Z", "p10": 318, "p50": 340, "p90": 362, "level": "ELEVATED", "risk_score": 0.17, "is_fallback": false },
        { "horizon_min": 15, "target_time": "2027-03-12T14:07:00Z", "p10": 360, "p50": 418, "p90": 470, "level": "HIGH",     "risk_score": 0.76, "is_fallback": false },
        { "horizon_min": 30, "target_time": "2027-03-12T14:22:00Z", "p10": 330, "p50": 405, "p90": 489, "level": "HIGH",     "risk_score": 0.70, "is_fallback": false }
      ]
    }
  ]
}
```
Errors: 404 event; 200 with empty `zones` and `issued_at: null` if no cycle has run.

### 3.12 `GET /api/predictions/{event_id}/zones/{zone_id}`

Query: `horizon_min` (5|15|30), `from`, `to`. Returns predictions whose `target_time` falls in range, joined with actual observed occupancy at `target_time` (if available) — powers predicted-vs-actual charts.

### 3.13 `GET /api/alerts/{event_id}`

Query: `status` (repeatable), `level`, `zone_id`, `limit`, `cursor`.
Response 200:
```json
{
  "alerts": [
    {
      "alert_id": 88, "zone_id": 2, "zone_code": "C1", "alert_type": "PREDICTED",
      "level": "HIGH", "horizon_min": 15, "predicted_onset": "2027-03-12T14:07:00Z",
      "trigger_value": 0.836, "status": "OPEN",
      "message": "Central Corridor predicted HIGH (84% of capacity) in 15 min",
      "opened_at": "2027-03-12T13:53:10Z", "acknowledged_at": null, "acknowledged_by": null
    }
  ],
  "next_cursor": null
}
```

### 3.14 `POST /api/alerts/{alert_id}/acknowledge` / `resolve`

Request (optional): `{ "note": "Two stewards sent to C1" }` (≤ 500 chars).
Response 200: updated alert. Errors: 409 if transition invalid (e.g. acknowledging a RESOLVED alert); 403 if operator not assigned to the event. Each call writes `audit_log`.

### 3.15 `POST /api/models/{model_version_id}/activate`

Response 200: `{ "model_version_id": 5, "is_active": true, "previous_active": 4 }`. Validation: artefact files exist and manifest feature set is supported. Error 422 otherwise.

### 3.16 `GET /api/health`

```json
{ "status": "ok", "db": "ok", "last_prediction_cycle": "2027-03-12T13:52:10Z", "version": "0.1.0" }
```

## 4. Consistency with the database

| API resource | Table(s) |
|---|---|
| users | `users` |
| venues, zones, connections | `venues`, `zones`, `zone_connections` |
| events, schedule, operators | `events`, `event_schedule_items`, `event_operators` |
| cameras, regions, lines | `camera_sources`, `camera_zone_regions`, `counting_lines` |
| observations, current, history | `crowd_observations` |
| predictions | `predictions`, `model_versions` |
| alerts | `congestion_alerts`, `audit_log` |

## 5. Rate limits and sizes

| Endpoint | Limit |
|---|---|
| `/api/auth/login` | 5 failures / 10 min / email+IP |
| `/api/crowd/observations` | 1,000 rows per request; 60 requests/min per key |
| Uploads | 5 MB |

## 6. Implementation amendments (v0.2, 2026-11-20)

Decisions taken while implementing WORKFLOW 2.3.2–2.3.4. Where this section and §1–§5 differ, this section wins.

| Topic | v0.1 text | Implemented |
|---|---|---|
| Authentication (D7) | JWT + roles; 401/403/429 errors; `created_by` on events; 404 for unassigned operators | No auth. `/api/auth/*`, `/api/users*` and `/api/events/{id}/operators` are not built; 401/403/429 never returned; `created_by` removed from event responses |
| Creating venues, zones, connections, events, schedule items | `POST` endpoints (§3.2, §3.5, §3.7) | Not built in the solo scope: configuration is loaded from YAML ([12 §6.1–6.2](12_DATASET_AND_DATA_COLLECTION.md)) with `tools/load_config.py`. Read endpoints only |
| Extra error codes | — | `405 METHOD_NOT_ALLOWED`, `503 SERVICE_UNAVAILABLE` use the same envelope; every response (success or error) carries `X-Request-ID` equal to `error.request_id` |
| `GET /api/health` (§3.16) | status code not stated | `200` with `status: "ok"` when the DB answers; **`503`** with `status: "error", db: "error"` when it does not. `last_prediction_cycle` = latest `predictions.issued_at`, `null` before any cycle |
| `GET /api/venues/{id}/zones` (§3.6) | `neighbours` ids; `thresholds.source` | `neighbours.in/out` list **zone ids only**; the virtual outside node is not listed (use `is_entry` / `is_exit`). `thresholds.source` is `DEFAULT` (no override stored) or `ZONE` (≥ 1 override) |
| `GET /api/venues/{id}/connections` | shape not given | `{venue_id, connections: [{connection_id, from_zone_id, to_zone_id, boundary_width_m, travel_time_s, bidirectional}]}`; `null` zone id = outside |
| `GET /api/venues/{id}/graph/validate` | shape not given | `{venue_id, valid, issues: [{code, severity, subject, message}]}`; codes `ISOLATED`, `UNREACHABLE`, `NO_PATH_OUT` (ERROR), `NO_COUNTING_LINE` (WARNING, only once cameras are configured) |
| `GET /api/events` | pagination per §1 | `{events: [...], next_cursor}`; newest first (by id); `limit` 1–500 (default 50); `cursor` is opaque — pass back the returned `next_cursor` |
| `GET /api/events/{id}` (§3.3) | — | as specified, without `created_by`; `active_model` is `null` until a model is activated |
| `PATCH /api/events/{id}` (§3.4) | 422 "with graph issues" | Body `{status}` only (other fields unknown → 422). Graph failure → `422 VALIDATION_ERROR`, message `venue graph is not valid`, `details[]` = `{field: <zone code or "venue">, issue: "<CODE>: <message>"}`. Each transition writes an `audit_log` row (`actor = USER`, `action = EVENT_STATUS`) |
| `GET /api/events/{id}/schedule` | shape not given | `{event_id, items: [{item_id, zone_id, zone_code, title, category, start_time, end_time, expected_attendance, attraction_weight}]}` in start order; `zone_id`/`zone_code` `null` = venue-wide |

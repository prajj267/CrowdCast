# 06 — Software Requirements Specification (SRS)

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed baseline for the 8-week prototype |
| Priority scheme | **M** = Must (core), **S** = Should, **C** = Could (extension), **W** = Won't (this phase) |

---

## 1. Introduction

### 1.1 Purpose
Defines the functional and non-functional requirements of the CROWDCAST prototype. Every requirement has a unique ID, a priority and a measurable acceptance criterion. IDs are referenced from the module design ([08](08_MODULE_DESIGN.md)), API ([14](14_API_SPECIFICATION.md)) and tests ([17](17_TESTING_STRATEGY.md)).

### 1.2 Definitions
| Term | Definition |
|---|---|
| Zone | A bounded venue area treated as one node $i \in V$ |
| Observation | One per-minute record of $X_i(t)$ for a zone |
| Prediction cycle | The scheduled job (every 60 s) that produces forecasts for all zones and horizons |
| Occupancy ratio | $u_i(t) = N_i(t) / C_i$ |
| Congestion level | `NORMAL`, `ELEVATED`, `HIGH`, `CRITICAL` (thresholds in [11 §4](11_SPATIAL_INTELLIGENCE.md)) |
| Data origin | `REAL` (CV on real video), `MANUAL` (human annotation), `SYNTHETIC` (simulator) |

### 1.3 User roles

| Role | Code | Permissions summary |
|---|---|---|
| Administrator | `ADMIN` | Everything, including users, cameras, model activation, retention |
| Event organiser | `ORGANISER` | Venues, zones, connections, events, schedules, thresholds; read monitoring data for own events |
| Monitoring operator | `OPERATOR` | Read live/predicted data and history for assigned events; acknowledge/resolve alerts |
| Ingestion service | `SERVICE` | Non-human; may only post observations and read configuration of its cameras |

Full permission matrix: [19 §3](19_SECURITY_AND_PRIVACY.md).

---

## 2. Functional requirements

### 2.1 Authentication and users (FR-AUTH)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-AUTH-01 | Users log in with email and password and receive a JWT access token | M | Valid credentials → 200 with token; invalid → 401; 5 failed attempts in 10 min → 429 |
| FR-AUTH-02 | Role-based access is enforced on every endpoint | M | Automated matrix: each role × each endpoint returns expected 2xx/403 |
| FR-AUTH-03 | Administrators create, deactivate and assign roles to users | M | Deactivated user's refresh rejected immediately; access token expires ≤ 15 min |
| FR-AUTH-04 | Ingestion services authenticate with a scoped API key | M | Key can call `POST /api/crowd/observations` and read own camera config only; else 403 |

### 2.2 Event management (FR-EVT)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-EVT-01 | Organisers create an event with name, venue, start/end time, expected attendance | M | Created event retrievable; `end_time > start_time` enforced |
| FR-EVT-02 | Event status moves `PLANNED → LIVE → ENDED` | M | Invalid transitions rejected with 409 |
| FR-EVT-03 | Organisers add schedule items (title, category, zone, start/end, expected attendance, attraction weight) | M | Items outside the event window rejected (422) |
| FR-EVT-04 | Schedule items editable during a live event; changes used in the next prediction cycle | M | Edited item reflected in features within 60 s |
| FR-EVT-05 | Organisers assign operators to an event | S | Operator sees only assigned events |

### 2.3 Venue and zone configuration (FR-VEN, FR-ZON)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-VEN-01 | Organisers create a venue with name, address, optional floor-plan image | M | PNG/JPEG/SVG ≤ 5 MB accepted |
| FR-ZON-01 | Organisers define zones with code, name, type, usable area (m²), planning capacity, polygon on floor plan | M | Area > 0; capacity > 0; polygon valid (≥ 3 vertices, non-self-intersecting) |
| FR-ZON-02 | If capacity omitted, system computes $C_i = \lfloor A_i \cdot \rho_{plan} \rfloor$ | M | Venue-level $\rho_{plan}$ configurable; stored value visible |
| FR-ZON-03 | Organisers define connections between zones with boundary width (m), travel time (s), directionality | M | Self-loops rejected (422); duplicates rejected (409) |
| FR-ZON-04 | Organisers mark zones as entry/exit (connected to "outside") | M | Graph validation reports ≥ 1 entry zone |
| FR-ZON-05 | System validates the venue graph (isolated / unreachable zones) | S | Validation endpoint lists problems |
| FR-ZON-06 | Organisers override congestion thresholds per zone | S | Overrides stored; defaults used otherwise |

### 2.4 Video ingestion (FR-VID)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-VID-01 | Administrators register camera sources (file path or RTSP URL) for a venue | M | Credentials in URLs stored encrypted, never returned by the API |
| FR-VID-02 | Recorded files replay at real-time speed with a configurable start timestamp mapped to event time | M | 10-min file produces observations spanning 10 event-minutes ± 1 |
| FR-VID-03 | Administrators define zone regions (polygons) and counting lines in image coordinates | M | Stored with camera, zone/connection and direction |
| FR-VID-04 | Live RTSP streams supported | C | Reconnects within 30 s after interruption |
| FR-VID-05 | Multiple cameras processed concurrently | M | ≥ 2 recorded streams simultaneously on the reference machine |

### 2.5 Computer vision (FR-CV)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-CV-01 | Detect persons in sampled frames (default 5 FPS) | M | Detector runs on every sampled frame |
| FR-CV-02 | Track persons with a motion-based tracker (ByteTrack) | M | No appearance embeddings computed or stored |
| FR-CV-03 | Count persons inside each zone region per frame | M | Count = tracked foot-points inside polygon |
| FR-CV-04 | Count directional crossings of counting lines | M | ≤ 1 crossing per track per line per direction within a 10-s debounce |
| FR-CV-05 | Flag low-confidence windows (high density / small boxes) | S | `quality = LOW_CONFIDENCE` stored on observation |
| FR-CV-06 | Density-map counter for regions flagged dense | C | Per-region switch; `method = DENSITY_MAP` stored |

### 2.6 Crowd observations (FR-OBS)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-OBS-01 | One observation per zone per minute per origin | M | Unique key (event, zone, bucket_start, origin) |
| FR-OBS-02 | Store occupancy, inflow, outflow, mean speed (nullable), quality, origin, method | M | Non-negative constraints |
| FR-OBS-03 | Batch ingestion via API (CV worker, simulator, CSV import) | M | 500 rows ingested in < 2 s |
| FR-OBS-04 | Missing minutes marked explicitly | M | Gap job inserts `quality = MISSING` rows |
| FR-OBS-05 | Import manual annotations from CSV | M | Stored with origin `MANUAL` |

### 2.7 Forecasting (FR-FC)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-FC-01 | Every 60 s during a LIVE event, predict $\hat N_i(t+h)$ for all zones, $h \in \{5,15,30\}$ | M | $|V| \times 3$ rows per cycle |
| FR-FC-02 | Each prediction includes P10, P50, P90 | M | P10 ≤ P50 ≤ P90 always |
| FR-FC-03 | Each prediction records model version | M | FK to `model_versions` non-null |
| FR-FC-04 | Persistence fallback on model failure or insufficient history | M | Fault test yields `is_fallback = true` predictions |
| FR-FC-05 | Administrators activate a trained model version | M | Next cycle uses new version |
| FR-FC-06 | Offline training reproducible from config + seed | M | Two runs give identical metrics (float tolerance) |

### 2.8 Congestion classification (FR-CNG)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-CNG-01 | Classify current and predicted level from $u$ thresholds | M | Unit tests at each boundary |
| FR-CNG-02 | Zone risk score combining predicted ratio and upper quantile | S | Score in [0, 1]; formula in [08 §M7](08_MODULE_DESIGN.md) |
| FR-CNG-03 | Thresholds configurable per zone | S | See FR-ZON-06 |

### 2.9 Alerts (FR-ALR)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-ALR-01 | Raise `PREDICTED` alert when predicted P50 level ≥ HIGH at horizon $h$ in 2 consecutive cycles; raise `CURRENT` alert when current level ≥ HIGH | M | Scripted episode triggers exactly one alert |
| FR-ALR-02 | Lifecycle `OPEN → ACKNOWLEDGED → RESOLVED` | M | Transitions logged with user and time |
| FR-ALR-03 | Auto-resolve after 3 consecutive cycles below (threshold − hysteresis margin) | M | Oscillating input produces no flapping |
| FR-ALR-04 | At most one open alert per (event, zone, alert type) | M | Partial unique index |
| FR-ALR-05 | New alerts visible on dashboard within 15 s | M | E2E latency test |
| FR-ALR-06 | Optional audible cue on CRITICAL | C | UI toggle |

### 2.10 Dashboard (FR-DSH)

| ID | Requirement | Pri | Acceptance criterion |
|---|---|---|---|
| FR-DSH-01 | Login page | M | Redirect to events after login |
| FR-DSH-02 | Event management (list, create, edit, schedule) | M | CRUD E2E tests pass |
| FR-DSH-03 | Venue configuration with zone polygon and connection editor | M | Zones drawable on floor plan |
| FR-DSH-04 | Live monitoring: map coloured by level, occupancy, heatmap, active alerts | M | Refresh ≤ 10 s |
| FR-DSH-05 | Prediction dashboard: forecast timeline with P10–P90 band, horizon selector | M | All 3 horizons available |
| FR-DSH-06 | Historical analytics: occupancy vs time, predicted vs actual, peaks | M | Any ended event viewable |
| FR-DSH-07 | Alerts page with filters and acknowledgement | M | Acknowledge reflected ≤ 2 s |
| FR-DSH-08 | Severity shown by colour **and** text/icon | M | WCAG 2.1 AA contrast |

---

## 3. Non-functional requirements

| ID | Category | Requirement | Pri | Acceptance criterion |
|---|---|---|---|---|
| NFR-MOD-01 | Modularity | Modules M1–M9 interact only through interfaces in [08](08_MODULE_DESIGN.md) | M | `import-linter` contracts pass in CI |
| NFR-MNT-01 | Maintainability | Python typed and linted (ruff, mypy); TypeScript strict | M | CI green |
| NFR-MNT-02 | Maintainability | Unit-test line coverage ≥ 70 % for M3, M5, M6, M7 | S | Coverage report |
| NFR-MNT-03 | Maintainability | Versioned migrations (Alembic) | M | Fresh DB to head in one command |
| NFR-PERF-01 | Prediction latency | Full cycle (≤ 15 zones × 3 horizons × 3 quantiles) ≤ 5 s | M | Timed on reference machine |
| NFR-PERF-02 | API latency | p95 ≤ 300 ms for reads at 20 concurrent users | M | Locust test |
| NFR-PERF-03 | CV throughput | ≥ 5 processed FPS per stream for 2 streams (`yolo11n`, 640 px, reference GPU) | S | Benchmark log |
| NFR-PERF-04 | Freshness | Minute boundary → visible on dashboard ≤ 20 s | M | E2E measurement |
| NFR-REL-01 | Reliability | Loss of one stream does not stop others or the prediction cycle | M | Fault injection |
| NFR-REL-02 | Reliability | Cycle failure → persistence fallback + error log | M | See FR-FC-04 |
| NFR-REL-03 | Reliability | Backend restart loses no persisted data | M | Kill/restart test |
| NFR-SCL-01 | Scalability (prototype) | 1 live event, ≤ 15 zones, ≤ 4 streams, ≥ 12 h per-minute data | M | Synthetic load test |
| NFR-SCL-02 | Scalability | ≈ 1.1 M observation rows; per zone-event query ≤ 1 s | S | Index benchmark |
| NFR-PRV-01 | Privacy | No facial recognition, no face crops, no appearance embeddings | M | Code review + schema inspection |
| NFR-PRV-02 | Privacy | Only aggregates persisted; track IDs in memory only | M | No track-level table in schema |
| NFR-PRV-03 | Privacy | Raw video retained ≤ 30 days unless consented research annotation | M | Retention job log |
| NFR-SEC-01 | Security | Passwords hashed with Argon2id | M | Unit test |
| NFR-SEC-02 | Security | HTTPS for all non-localhost traffic | M | Reverse-proxy config |
| NFR-SEC-03 | Security | Schema validation on all inputs | M | Negative API tests |
| NFR-USE-01 | Usability | Operator identifies most at-risk zone within 10 s | S | Walkthrough, 5 participants |
| NFR-PORT-01 | Portability | `docker compose up` on Windows/Linux/macOS | M | Fresh-machine test |

**Reference machine:** 6-core CPU, 16 GB RAM, NVIDIA GPU ≥ 6 GB VRAM. Exact hardware recorded in the evaluation report.

---

## 4. Traceability summary

| Objective | Requirements | Module | Tests |
|---|---|---|---|
| O1 | FR-CV-01…03, 05 | M2 | TC-CV-01…03 |
| O2 | FR-CV-04 | M2 | TC-CV-04…06 |
| O3 | FR-OBS-* | M3, M4 | TC-OBS-* |
| O4 | FR-FC-* | M6 | TC-ML-* |
| O5 | FR-CNG-* | M7 | TC-CNG-* |
| O6 | FR-ALR-* | M7 | TC-ALR-*, TC-E2E-03 |
| O7 | FR-DSH-* | M9 | TC-FE-*, TC-E2E-* |

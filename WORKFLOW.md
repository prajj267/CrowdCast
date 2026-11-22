# CROWDCAST — Solo Workflow Tracker

> The single place where progress is tracked. Tick a box only when its task meets the **Definition of done** (§ end).
> Scope is the **solo, CPU-only** version of the documented design. Where this file and `DOCUMENTATION/` disagree on *scope*, this file wins; the documents remain the source of truth for *contracts and methods* (schemas, API, formulas, evaluation).

**Developer:** 1 person · **Machine:** Windows 11 laptop, Ryzen 7 8840HS (8c/16t), 31 GB RAM, AMD Radeon 780M iGPU (**no CUDA**), ~41 GB free disk
**Plan length:** ≈ 50 working days (≈ 10 weeks at 5 days/week), including the React dashboard (D1). This is tight. If you fall behind, trim in this order: RF model → V3 topology volume → own footage → History page → Event/venue page (keep Live, Predictions and Alerts).

---

## Status at a glance

Update the Status column as you go: `Not started` / `In progress` / `Done` / `Blocked`.

| Phase | Name | Target week | Est. days | Milestone | Status |
|---|---|---|---|---|---|
| 0 | Decisions, approvals, scope update | 0 | 2 | MS0 | Not started |
| 1 | Foundations (repo, env, DB) | 1 | 3 | MS1 | Done (MS1) |
| 2 | Venue graph and configuration | 1–2 | 3 | — | Done |
| 3 | CROWDSIM v1 and ingestion | 2 | 5 | — | Done |
| 4 | Vertical slice (baselines, risk, React scaffold + live page) | 3 | 7 | **MS2** | Done (MS2) |
| 5 | Forecasting core (features, XGBoost) | 4 | 5 | — | Done |
| 6 | CV pipeline on CPU | 5 | 6 | **MS3** | Done (MS3) |
| 7 | Data, experiments, evaluation | 6–7 | 9 | **MS4** | In progress |
| 8 | Dashboard completion (React) | 8–9 | 6 | — | In progress |
| 9 | Hardening, report, demo | 9–10 | 4 | **MS5** | Not started |
| X | Extensions (gated) | buffer | — | MS6 | Not started |

**Current focus:** Phase 7 runs (machine) + Phase 8 dashboard in parallel (Phase 0 still open: doc updates 0.3.x)
**Next task:** 7.3.2 SYN-noisy tuning run (running), then tuned validation ablations clean + noisy with `--params` (closes 7.3.1–7.3.3) (Phase 7)

---

## Solo scope (what changed from the team plan)

| Area | Documented (team) plan | Solo plan |
|---|---|---|
| Team | 4 roles, ≈ 108 person-days | 1 person, ≈ 45 days |
| CV hardware | NVIDIA GPU, near-real-time | CPU only, **offline** on recorded clips; the demo replays stored observations (AS4 / R6 fallback) |
| Detector | YOLO11 (GPU) | YOLOX-nano/tiny/s (Apache-2.0, D2) run with ONNX Runtime on the CPU; frames sampled (e.g. 2–5 FPS); ByteTrack from a permissively licensed implementation |
| Processes | api + scheduler + cv-worker in Docker Compose | Postgres in Docker; Python runs natively; scheduler runs in-process or as a CLI loop |
| Auth | JWT, refresh cookies, Argon2id, 4-role RBAC | **None** (D7): single local user; no login page; listed as a limitation |
| Dashboard | React + TS, 7 pages, polygon editor | React 18 + TypeScript + Vite (D1) with TanStack Query, Recharts and Tailwind, per [15](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md); 5 pages (Live, Predictions, Alerts, History, Event/venue); no login page unless D7 needs one; **no polygon editor** (venue and camera configuration via YAML import) |
| Models | Baselines, XGBoost, RF, LSTM, GNN | Baselines B0–B3 + XGBoost quantile (RF optional); LSTM and GNN become extensions |
| Real data | Staged session with 30–80 volunteers + campus event | **Public datasets only** (D6): Mall, ShanghaiTech B and MOT20 for CV evaluation; no REAL forecasting dataset, so forecasting conclusions are synthetic evidence |
| Evaluation | Usability walkthrough with 5 people | Optional and informal |
| Testing | Playwright E2E, Locust | Scripted end-to-end smoke test + timing check of the prediction cycle |

---

## Decision log

| ID | Decision | Options | Default / recommendation | Final | Date |
|---|---|---|---|---|---|
| D1 | Dashboard technology | Streamlit / React + TS | Streamlit (saves ≈ 2–3 weeks) | **React 18 + TypeScript + Vite** (stack per [15](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md)); reduced to 5 pages, no polygon editor | 2026-11-20 |
| D2 | Detector licence | Ultralytics (AGPL-3.0) / YOLOX (Apache-2.0) | Ultralytics if the institution accepts AGPL | **YOLOX** via ONNX Runtime on CPU; ByteTrack from a permissively licensed implementation (licence checked before adding). Ultralytics not used | 2026-11-20 |
| D3 | Repository visibility | Public / private | Private until the report is submitted | **Public GitHub repo** `prajj267/CrowdCast` (changed from private on 2026-11-20 at the developer's request); CI with GitHub Actions | 2026-11-20 |
| D4 | Demo venue | V1 college festival / own layout | V1 from [11 §6](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md) | **Split demo:** the CV part runs on public dataset clips (Mall, MOT20) with zones drawn on the camera view; the forecasting and alert part runs on synthetic V1, because no public dataset has a venue graph or an event schedule | 2026-11-20 |
| D5 | Start date and hard deadline | — | — | **No hard deadline**; started 2026-11-20; ≈ 10-week target, self-paced. Extensions may run once MS5 is met | 2026-11-20 |
| D6 | Real data | Small staged session / public datasets only | Request approval now; fall back to public data | **Public datasets only**: no own recordings; forecasting results are synthetic only | 2026-11-20 |
| D7 | Authentication | None / single user / full JWT | None, stated as a limitation | **No auth**: single local user; FR-AUTH out of scope, stated as a limitation | 2026-11-20 |
| D8 | Python environment tool | uv / venv + pip | uv | **uv** 0.13.9 (installed with winget) | 2026-11-20 |

## Deviation log

Record every departure from the documented plan (method, volume, threshold, trial count…), so the report can state it.

| Date | Doc / section | Planned | Actual | Reason |
|---|---|---|---|---|
| 2026-11-20 | [experimental_design §2](RESEARCH/experimental_design.md), [12 §4](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md) | REAL-staged and REAL-event datasets as a real-data test | Dropped; no REAL forecasting data | D6: public datasets only. H6 and H7 are tested on SYN-noisy only; the real-data parts (and the "H1 rejected on real data" check) cannot be run, and the report must say so |
| 2026-11-20 | [16 §2.2](DOCUMENTATION/16_MODEL_EVALUATION.md), O2 | Flow error on ≥ 60 min of our own annotated footage | Flow error on public sequences with virtual counting lines (ground truth from annotated tracks), if feasible | D6 |
| 2026-11-20 | [06 FR-AUTH](DOCUMENTATION/06_REQUIREMENTS_SPECIFICATION.md), [13](DOCUMENTATION/13_DATABASE_DESIGN.md), [14](DOCUMENTATION/14_API_SPECIFICATION.md), [19 §3](DOCUMENTATION/19_SECURITY_AND_PRIVACY.md) | JWT auth + 4-role RBAC | No auth | D7: solo scope |
| 2026-11-20 | [09 §4](DOCUMENTATION/09_COMPUTER_VISION_METHODOLOGY.md) (CV-01) | Ultralytics YOLO11 + built-in ByteTrack | YOLOX via ONNX Runtime + standalone ByteTrack | D2: licence (Apache-2.0 instead of AGPL-3.0) |
| 2026-11-20 | [09 §3](DOCUMENTATION/09_COMPUTER_VISION_METHODOLOGY.md), WORKFLOW 1.4.2 | Detector input 640 px (or 960 px) chosen per camera; benchmark every model at 416 and 640 px | The official YOLOX ONNX files have fixed inputs (nano/tiny 416, s 640); each model is used and benchmarked at its export size only | Other sizes need a re-export with PyTorch (heavy dependency); not justified unless measured recall requires it |
| 2026-11-21 | [09 §5, §11](DOCUMENTATION/09_COMPUTER_VISION_METHODOLOGY.md), WORKFLOW 6.2.2 | ByteTrack from a permissively licensed library (`supervision`, MIT) | ByteTrack algorithm implemented in `crowdcast/vision/tracking.py` (Kalman + two-stage IoU association, scipy assignment) | `supervision` would add 9 runtime packages (PyAV, matplotlib, Pillow, requests, …) for one ~150-line algorithm; in-house code is fully explainable and motion-only by construction. Doc 09's "match IoU 0.8" read as ByteTrack's match_thresh 0.8 on cost 1 − IoU |
| 2026-11-21 | [10 §5.1, §3.4](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md) | `fused_u_t` = complementary filter recursing from the event start | Recursion over a fixed 60-min look-back for every row | A live cycle sees only 60 min; with this definition training and online give identical values (tested) |
| 2026-11-21 | [10 §5.4](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md) | `nbr_flow_to_i` = flow from neighbours over shared lines | Not built; `nbr_out_pressure` kept (zone outflows × shares estimated on training events) | The ingestion contract (AD-02) stores zone inflow/outflow, not per-connection flows, so the feature could not be computed online |
| 2026-11-20 | [14 §2, §3.2/3.5/3.7](DOCUMENTATION/14_API_SPECIFICATION.md) | POST endpoints to create venues, zones, connections, events and schedule items | Read endpoints + status transitions only; configuration loaded from YAML (`tools/load_config.py`); amendments in doc 14 §6 | Solo scope: no polygon/venue editor (D1 scope note), YAML import already planned |
| 2026-11-20 | [09 §2–4](DOCUMENTATION/09_COMPUTER_VISION_METHODOLOGY.md), WORKFLOW 1.4.3 | Whole frame resized to the detector input | **Tiled detection** (`crowdcast/vision/tiling.py`): overlapping tiles at the model input size (overlap 0.2), drop boxes cut at inner tile edges, one full-frame pass, merge NMS. **Provisional default: YOLOX-s + tiles at 5 FPS** (≈ 3 s processing per video second, offline); YOLOX-nano + tiles (≈ real time) as fast fallback. Final model choice by accuracy on MOT20 in 7.1 | Untiled models detect few of the small, distant people in 1080p wide shots (bench-20261120T134304Z: 0.9–8.5 detections/frame untiled vs 44.8–61.8 tiled); accuracy not yet measured |
| 2026-11-21 | [12 §5.3](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md), [16 §2.1](DOCUMENTATION/16_MODEL_EVALUATION.md), WORKFLOW 7.2.2 | Occupancy noise m(ρ) = m0 + m1·ρ calibrated against density ρ (persons/m²) | ρ per public-data sample taken from doc 16's count-band ↔ density-band pairing (band midpoints 0.25 / 1.0 / 2.25 / 3.5); crossing parameters from 1.9 min of MOT20 (p_det essentially from MOT20-03 alone; r_fp = 0 with a weak upper bound) | The public datasets have no calibrated ground-plane areas; this is an assumption and is reported as one. 7.2.1 and 7.2.4 were already done in Phase 5 (V2/V3, frozen splits) |
| 2026-11-21 | [10 §8.3](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md), [experimental_design §5](RESEARCH/experimental_design.md) | Optuna TPE 50 trials, GroupKFold 5 folds per (config, horizon) | **20 trials, 3 folds** for every one of the 15 cells (same budget for all, so the ablation stays fair); search space unchanged; early stopping on the held-out fold; objective = mean per-event MAE of the median model | CPU only: the full plan was estimated at roughly 20–40 h per dataset variant (rough estimate from measured fit times, not a measurement); budget chosen by the developer |
| 2026-11-22 | [16 §5](DOCUMENTATION/16_MODEL_EVALUATION.md) | Replay test events through the running M6 + M7 code (prediction cycle and risk engine writing `congestion_alerts`) | Offline replay: per-row forecasts saved by the ablation runner, fed minute by minute into the real M7 state machine `risk.alerts.decide` (same confirmation, hysteresis and escalation); the DB wrapper `risk/engine.py` and the API are bypassed. Rows exist only while t + h is inside the event, so the last h minutes have no h-minute forecast | A DB replay of 78 test events × 9 models through Postgres is many hours on this laptop; `engine.py` only rebuilds the same 3-cycle signals and stores what `decide` returns. Live-cycle behaviour stays demonstrated by the Phase 5 exit replay (exit53-demo) |

---

## Phase 0 — Decisions, approvals, scope update (MS0)

### 0.1 Decisions
- [ ] 0.1.1 Fill decisions D1–D8 in the Decision log
- [ ] 0.1.2 Get supervisor sign-off on the solo scope, the dashboard choice and the licence (D1, D2, D7)

### 0.2 Approvals and data (slow; start early)
- [ ] 0.2.1 ~~Submit the ethics/recording application~~ Not needed (D6: no own recordings). Instead, confirm with your supervisor that using public research datasets needs no approval.
- [ ] 0.2.2 Read and record the licence terms of Mall, ShanghaiTech Part B and MOT20; change [K] tags to [V] in [12 §2](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md) where confirmed

### 0.3 Bring the documentation in line with the solo scope (R16)
- [ ] 0.3.1 [02 Objectives and Scope](DOCUMENTATION/02_OBJECTIVES_AND_SCOPE.md): move LSTM, auth/RBAC and the usability test to extended or out of scope
- [ ] 0.3.2 [21 Roadmap](DOCUMENTATION/21_DEVELOPMENT_ROADMAP.md) and [milestones.md](PROJECT_MANAGEMENT/milestones.md): point to this file
- [ ] 0.3.3 [team_responsibilities.md](PROJECT_MANAGEMENT/team_responsibilities.md): one-person note; [risk_register.md](PROJECT_MANAGEMENT/risk_register.md): R6 has occurred, R9 changes to "single developer unavailable"
- [ ] 0.3.4 [INDEX §7.2](DOCUMENTATION/INDEX.md): record answers to the open team decisions

**Exit:** D1–D8 filled, ethics application submitted, documents state the solo scope.

---

## Phase 1 — Foundations (MS1)

### 1.1 Repository
- [x] 1.1.1 `git init`; `.gitignore` covers `data/`, `videos/`, `*.mp4`, `*.avi`, `models/`, `*.pt`, `*.onnx`, `.env`, `__pycache__/`, `.venv/`, `runs/`
- [x] 1.1.2 Create the code layout from [07 §7](DOCUMENTATION/07_SYSTEM_ARCHITECTURE.md): `backend/crowdcast/{ingestion,vision,aggregation,storage,venue_graph,forecasting,risk,api,common}`, `backend/tools/{crowdsim,training}`, `backend/tests`, `frontend/`, `configs/`
- [x] 1.1.3 Create `EXPERIMENT_LOG.md` (columns: date, config, data, seed, result path, deviation)

### 1.2 Python environment and tooling (T1.1)
- [x] 1.2.1 Python 3.12 environment (D8); `pyproject.toml` with pinned dependencies
- [x] 1.2.2 ruff, mypy, pytest, pre-commit configured; a single command runs all checks
- [x] 1.2.3 `common/config.py` (pydantic-settings, reads `.env`); `.env.example` committed
- [x] 1.2.4 `common/time.py`: UTC everywhere, minute-aligned buckets, event-time helpers

### 1.3 Database (T1.2, T1.3)
- [x] 1.3.1 `docker-compose.yml` with `postgres:16` only, a named volume and a health check
- [x] 1.3.2 SQLAlchemy 2 models for the tables in [13 §3](DOCUMENTATION/13_DATABASE_DESIGN.md), minus those removed by D7, with the enums from §2 and the indices from §5
- [x] 1.3.3 Alembic migration v1; `alembic upgrade head` on an empty database works
- [x] 1.3.4 Note any schema change caused by D7 in [13](DOCUMENTATION/13_DATABASE_DESIGN.md)

### 1.4 CV environment smoke test (T1.8, adapted to CPU)
- [x] 1.4.1 Install onnxruntime (CPU); get the official YOLOX ONNX models (nano/tiny/s) from the YOLOX repository releases, with the licence and source recorded; run on one image with YOLOX's pre/post-processing (letterbox, decode, NMS)
- [x] 1.4.2 Measure FPS of YOLOX-nano/tiny/s at their fixed export sizes (nano/tiny 416 px, s 640 px; see Deviation log) on a public sample clip (check download size first); record the results in `EXPERIMENT_LOG.md`
- [x] 1.4.3 Choose the model and frame-sampling rate from the measurements; record it in the Deviation log

**Exit (MS1):** `docker compose up -d` plus `alembic upgrade head` work; `pytest` passes; CPU detector speed measured and recorded.

---

## Phase 2 — Venue graph and configuration (M5)

### 2.1 Configuration formats
- [x] 2.1.1 Venue YAML schema (zones: code, type, area, capacity, polygon; connections: from, to, width, travel time, bidirectional), per [12 §6](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md)
- [x] 2.1.2 `configs/venues/v1.yaml` from [11 §6](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md) (illustrative values, labelled as such)
- [x] 2.1.3 Schedule YAML/CSV format and one example event schedule for V1

### 2.2 Venue graph module (M5)
- [x] 2.2.1 Graph construction and the validation rules in [11 §9](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md)
- [x] 2.2.2 Adjacency matrices and shortest-path travel times ([11 §5.3](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md))
- [x] 2.2.3 Unit tests from [17 §2.2](DOCUMENTATION/17_TESTING_STRATEGY.md) (TC-GR-01–03 done; TC-GR-04 needs simulator output → done with CROWDSIM in Phase 3)

### 2.3 Loading and API skeleton (T2.1, T2.2, T2.5)
- [x] 2.3.1 CLI: load venue YAML and event + schedule YAML into the database
- [x] 2.3.2 FastAPI app with `GET /api/health` and the error envelope ([14 §1.1](DOCUMENTATION/14_API_SPECIFICATION.md))
- [x] 2.3.3 Read endpoints: venues, zones, events; event status transitions ([14 §3.2–3.7](DOCUMENTATION/14_API_SPECIFICATION.md))
- [x] 2.3.4 API tests for these endpoints

**Exit:** loading `v1.yaml` creates 8 zones; `GET /api/venues/{id}/zones` returns them; graph validation rejects an invalid venue.

---

## Phase 3 — CROWDSIM v1 and ingestion (T1.6, T2.3, T2.4)

### 3.1 Ingestion contract (AD-02)
- [x] 3.1.1 `POST /api/crowd/observations` with every validation rule in [14 §3.8](DOCUMENTATION/14_API_SPECIFICATION.md): partial rejection, upsert, `data_origin` guard
- [x] 3.1.2 Tests: valid batch, partial rejection, wrong zone, unaligned bucket, SYNTHETIC posted to a non-synthetic event

### 3.2 CROWDSIM design (T1.6)
- [x] 3.2.1 Design note `backend/tools/crowdsim/DESIGN.md`: parameters, ranges and seeds; placeholder values clearly labelled

### 3.3 CROWDSIM core ([12 §5.1](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md))
- [x] 3.3.1 Arrivals (non-homogeneous Poisson) and agent state; tick δ = 10 s
- [x] 3.3.2 Destination choice (multinomial logit: attraction, distance, crowding)
- [x] 3.3.3 Movement along shortest paths with edge capacity, queueing and spillback
- [x] 3.3.4 Speed–density relation and departures (exit wave)
- [x] 3.3.5 Schedule perturbation: start offset U(−5, +10) min, popularity LogNormal(0, 0.3), 5 % pop-up events
- [x] 3.3.6 Per-minute output to Parquet (true N, flows, speed, published and actual schedule) per [12 §5.2, §6](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md)

### 3.4 Validity and replay
- [x] 3.4.1 Unit test: venue-level conservation holds exactly ([12 §5.5](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md))
- [x] 3.4.2 Plot occupancy profiles for one event and check them by eye; save the plot under `reports/figures/` (SYNTHETIC label on the figure)
- [x] 3.4.3 Replay client: posts minute buckets to the ingestion API at an adjustable speed-up, with `data_origin = SYNTHETIC`

**Exit:** a 6-hour V1 event generates in seconds and its replay appears in `crowd_observations`.

---

## Phase 4 — Vertical slice (MS2)

### 4.1 Baselines ([10 §2–3](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md), T3.7)
- [x] 4.1.1 B0 persistence, B1 moving average (k = 5), B2 linear trend (10 min), B3 conservation extrapolation
- [x] 4.1.2 Unit tests with hand-computed values

### 4.2 Prediction cycle (T3.1, [10 §12](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md))
- [x] 4.2.1 Cycle every 60 s of event time: read the latest observations, predict +5/+15/+30 min, write `predictions`
- [x] 4.2.2 Falls back to B0 when no active model exists or a model fails; the fallback is logged
- [x] 4.2.3 Works in replay mode (event time, not wall-clock time)

### 4.3 Risk engine (M7, T3.2)
- [x] 4.3.1 Level function and risk score ([08 M7](DOCUMENTATION/08_MODULE_DESIGN.md)); per-zone thresholds
- [x] 4.3.2 Alert state machine: CURRENT opens after 1 cycle; PREDICTED after 2 consecutive cycles; resolves after 3 cycles below threshold − 0.05; escalates to CRITICAL
- [x] 4.3.3 Tests from [17 §2.3](DOCUMENTATION/17_TESTING_STRATEGY.md), including flapping input

### 4.4 Read API
- [x] 4.4.1 `GET /api/crowd/current/{event_id}`, `/api/crowd/history/{event_id}`
- [x] 4.4.2 `GET /api/predictions/{event_id}` (and per zone), `GET /api/alerts/{event_id}`, acknowledge/resolve

### 4.5 React scaffold and minimal live page (D1 = React)
- [x] 4.5.1 Scaffold `frontend/` with Vite + React 18 + TypeScript, Tailwind, TanStack Query, React Router; ESLint + Prettier; `npm run build` and `npm run lint` pass
- [x] 4.5.2 Typed API client generated from FastAPI's OpenAPI schema (e.g. openapi-typescript), with a regeneration script; Vite dev proxy to the API
- [x] 4.5.3 Design tokens from [15 §2.1](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md) (level colours + icons, per [11 §4](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md)) and the app shell (layout, navigation, event selector)
- [x] 4.5.4 Live page: ZoneCards (occupancy, ratio, level) and AlertList, polling with TanStack Query
- [x] 4.5.5 VenueMap: SVG floor plan from zone polygons in the venue YAML, filled by level

**Exit (MS2):** replaying a synthetic event changes zone colours every minute; persistence predictions are stored; a surge opens a CURRENT alert.

---

## Phase 5 — Forecasting core (T3.6, T3.8)

### 5.1 Feature builder ([10 §5](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md))
- [x] 5.1.1 One shared `FeatureBuilder` used by both training and the online cycle
- [x] 5.1.2 F_HIST, F_FLOW, F_SCHED (published schedule only), F_NBR (graph-derived)
- [x] 5.1.3 Feature-set configs A1, A2, A3, A4, A4\NBR
- [x] 5.1.4 Target y = (N(t+h) − N(t)) / C, drop rows with t + h > T; forward-fill only ([10 §6–7](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md))

### 5.2 Leakage protection
- [x] 5.2.1 TC-ML-02: features from a truncated series equal features from the full series up to t
- [x] 5.2.2 Test that the actual (realised) schedule never reaches the features
- [x] 5.2.3 Splits by event only; a test fails if one event appears in two splits

### 5.3 XGBoost and registry
- [x] 5.3.1 XGBoost quantile regression (P10/P50/P90), direct multi-horizon; sort quantiles after the inverse transform
- [x] 5.3.2 Training CLI: build dataset → train → write a manifest (config, data hash, seed, git commit) → register in `model_versions`
- [x] 5.3.3 `POST /api/models/{id}/activate`; the online cycle uses the active model, with fallback to B0
- [x] 5.3.4 PREDICTED alerts driven by model forecasts

**Exit:** an XGBoost A4 model trained on a few V1 events is active; a scripted surge raises a PREDICTED alert before the CURRENT alert.

---

## Phase 6 — CV pipeline on CPU (M1–M3, T2.7, T3.4)

### 6.1 Video input (M1)
- [x] 6.1.1 `FrameSource` for video files with configurable frame sampling and a configured start time (event time, not wall-clock)
- [x] 6.1.2 Camera YAML: source file, start offset, regions (polygons per zone), counting lines

### 6.2 Detection and tracking (M2)
- [x] 6.2.1 `Detector` interface wrapping YOLOX (ONNX Runtime, CPU); person class only
- [x] 6.2.2 ByteTrack behind a `Tracker` interface, from a permissively licensed implementation (verify its licence before adding the dependency); motion-only, no appearance features
- [x] 6.2.3 Privacy check: no frames, crops or tracks written to disk; only aggregates

### 6.3 Counting and aggregation (M3, [09 §6](DOCUMENTATION/09_COMPUTER_VISION_METHODOLOGY.md))
- [x] 6.3.1 Occupancy per frame (foot point inside the polygon)
- [x] 6.3.2 Line crossings with direction and debounce
- [x] 6.3.3 Minute aggregation with quality flags; posts REAL observations to the ingestion API
- [x] 6.3.4 Geometry and aggregation unit tests ([17 §2.1](DOCUMENTATION/17_TESTING_STRATEGY.md)); one fixed-clip regression test

**Exit (MS3):** a recorded clip produces REAL observations end to end, together with Phase 5 complete.

---

## Phase 7 — Data, experiments and evaluation (MS4)

### 7.1 Public data and CV evaluation
- [x] 7.1.1 Download Mall, ShanghaiTech B (test split) and 2 MOT20 sequences; check disk space first; keep them outside git
- [x] 7.1.2 Count MAE by density band ([16 §2.1](DOCUMENTATION/16_MODEL_EVALUATION.md)); MOT20 tracking sanity check
- [x] 7.1.3 Flow error (O2): draw virtual counting lines on MOT20 scenes and compare detected crossings with crossings derived from the annotated ground-truth tracks (if feasible; otherwise log it as a deviation)

### 7.2 Synthetic datasets
- [x] 7.2.1 CROWDSIM v2: V2 and V3 topologies (T4.1)
- [x] 7.2.2 Noise model ([12 §5.3](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md)): occupancy parameters (m₀, m₁, σ_r) calibrated from count errors on public datasets (7.1.2); crossing parameters (p_det, r_fp) from 7.1.3 if it was feasible. Anything uncalibrated stays a labelled placeholder
- [x] 7.2.3 Generate SYN-clean and SYN-noisy (volume per [experimental_design §2](RESEARCH/experimental_design.md), or a documented reduction)
- [x] 7.2.4 **Freeze `splits.json` (seed 2027) and commit it before any training run**

### 7.3 Ablation study ([experimental_design §4–7](RESEARCH/experimental_design.md))
- [ ] 7.3.1 Ablation runner: configs A1–A4 and A4\NBR × horizons 5/15/30 × XGBoost (RF optional); baselines B0–B3 on every dataset
- [ ] 7.3.2 Tuning with GroupKFold by event and Optuna; reduce the trial count if CPU time requires it (Deviation log)
- [ ] 7.3.3 Split-conformal intervals calibrated on validation; coverage (H7)
- [ ] 7.3.4 Evaluate each test split **once** per final configuration; 3 seeds
- [ ] 7.3.5 Statistics: one-sided Wilcoxon, Holm correction, bootstrap CIs, post-release stratification (H1–H4, H6)

### 7.4 Classification and operational evaluation
- [ ] 7.4.1 Precision, recall and F1 for HIGH-or-above per horizon (O5)
- [ ] 7.4.2 Replay test events through M6 + M7: warning lead time, false-alarm rate, missed episodes (O6, T4.7)

### 7.5 Reporting
- [ ] 7.5.1 Fill the tables in [16](DOCUMENTATION/16_MODEL_EVALUATION.md) from pipeline output only, with SYNTHETIC and REAL kept separate
- [ ] 7.5.2 Every number traceable to an `EXPERIMENT_LOG.md` entry and a committed config

**Exit (MS4):** all evaluation tables filled from logged runs; hypotheses accepted or rejected with statistics; negative results reported.

---

## Phase 8 — Dashboard completion (React)

- [x] 8.1 Prediction view: Recharts forecast chart with the P10–P90 band and a horizon selector ([15 Page 5](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md))
- [x] 8.2 Alerts view: list, acknowledge and resolve ([15 Page 7](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md))
- [x] 8.3 History view with CSV export ([15 Page 6](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md))
- [x] 8.4 Event and venue view (read-only, YAML import)
- [ ] 8.5 Empty, stale-data and error states ([15 §4](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md)); data origin shown on screen (SYNTHETIC / REAL)
- [ ] 8.6 Component tests (Vitest + React Testing Library) for level colouring, the alert list and the empty and stale states ([17 §2.7](DOCUMENTATION/17_TESTING_STRATEGY.md))

**Exit:** the most at-risk zone can be found on the live view within seconds; every view handles missing data.

---

## Phase 9 — Hardening, report and demo (MS5)

- [ ] 9.1 Scripted end-to-end smoke test: fresh database → load venue → replay event → predictions → alerts
- [ ] 9.2 Timing check: one prediction cycle fits the budget in [07 §5](DOCUMENTATION/07_SYSTEM_ARCHITECTURE.md)
- [ ] 9.3 Privacy check: no footage, frames or personal data in git history; retention rules applied
- [ ] 9.4 Documentation consistency audit: docs match the code (R16); results inserted only from logged runs
- [ ] 9.5 Write the report, with limitations: solo scope, CPU only, no authentication, no own real-world recordings (forecasting evidence is synthetic), synthetic-to-real gap
- [ ] 9.6 Demo script, rehearsal, recorded demo video; run from a fresh clone following [18 §5](DOCUMENTATION/18_DEPLOYMENT_PLAN.md)

**Exit (MS5):** the demo runs from a fresh clone; the report cites only pipeline-produced results.

---

## Phase X — Extensions (start only when the gate is met)

| Extension | Gate ([milestones.md](PROJECT_MANAGEMENT/milestones.md)) | Status |
|---|---|---|
| LSTM | MS4 met and XGBoost A4 evaluated on SYN-noisy | Not started |
| GNN (A5) | LSTM done or skipped, ≥ 1 week left, A4 shows a neighbour gain | Not started |
| Density-map counter | CV evaluation shows a dense-band undercount that affects alerts | Not started |
| Live RTSP | Recorded pipeline stable for a 2-hour replay | Not started |

---

## Definition of done (every task)

1. Code committed; `ruff`, `mypy` and `pytest` pass.
2. Tests added for new logic.
3. If a contract changed (DB schema, API, observation JSON, YAML formats), the matching document (13 / 14 / 12) is updated in the same commit.
4. Any deviation from the documented method is in the Deviation log.
5. Any result is logged in `EXPERIMENT_LOG.md` and reproducible from committed code.

---

## Session log

Newest first. One line per working session.

| Date | Tasks worked | Done | Notes / blockers | Next |
|---|---|---|---|---|
| 2026-11-22 | 8.4 | Event & venue page (read-only): event facts + active model, venue-graph validation panel, published schedule as a per-zone `ScheduleStrip` + table, zones (type, area, capacity, thresholds with default/override), connections (width, travel time, direction); how to change it = YAML + `tools.load_config` (stated on the page). Placeholder page component removed (all five pages exist). 3 new tests (20 total); checked in the browser on event 1189 | No map on this page (Live has it); no create/edit forms (D1 scope: YAML import) | 8.5 states, 8.6 component tests |
| 2026-11-22 | 8.3 | History page: occupancy (% of capacity) over the whole event for up to 4 chosen zones (default: highest peaks) with schedule bands, HIGH line, crosshair tooltip, legend and direct labels at each peak; predicted vs actual for a chosen zone and horizon with P10–P90 band and MAE; peaks table (max, time, minutes at HIGH or CRITICAL); CSV export of the 1-min history (all zones, with data origin). Series colours = dataviz reference palette, validated light + dark (`--series-1..4`). 5 new tests (17 total); checked in the browser on event 1189 | MAE is computed in the browser from the timeline endpoint, not server-side as doc 15 says (same arithmetic, no API change). "Alert timeline vs episode onset" not built (the operational evaluation, 7.4, measures lead time) | 8.4 Event & venue page |
| 2026-11-22 | 8.2 | Alerts page: server-side filters (status, level, zone) + type filter, history table newest first with cursor "Load more", detail panel (trigger, horizon, predicted onset, timeline with event-time vs wall-clock labels) with acknowledge / resolve + optional note; shared `useAlertAction` hook (Live list refactored onto it). 5 new frontend tests (12 total); checked in the browser on event 1189 | Notes and the audit trail are written by the API but cannot be read back (no GET endpoint; adding one is a contract change - asked). No users column (D7). Toasts / CRITICAL sound not built | 8.3 History page |
| 2026-11-22 | 8.1 | Predictions page: zone selector (in the URL), `ForecastChart` (Recharts: observed last 60 min, P50 fan with P10–P90 band to +30 min, threshold lines, now marker, schedule bands), zone × horizon table (P50 + interval, level shape + word, risk, fallback flag, model version); page lazy-loaded (main bundle 664 → 225 kB). Added Recharts (D1) and Vitest + Testing Library (doc 17 §2.7); `npm run test` in `scripts/check.ps1`. 7 frontend tests; full check 311 backend (DB tests ran again, Docker up) + 7 frontend passed; checked in the browser on event 1189 | No "Why?" panel (feature attributions not stored; doc 15 makes it optional). `npm audit`: 2 moderate advisories in react-router 6 (open redirect via backslash in links; SSR hydration) — not fixed, needs the react-router 7 major upgrade; low impact for a local dashboard without login | 8.2 Alerts page |
| 2026-11-22 | 7.4.1, 7.4.2 (code) | `tools/training/operational.py`: P/R/F1 for ≥ HIGH per horizon and model (bootstrap CI over events), 4 × 4 confusion, PR curve on P50 / P90; offline alert replay through `risk.alerts.decide` → lead time (median, IQR), missed-episode and false-alarm rates, false alarms per hour, source mix. Ablation runner now saves `predictions.parquet`. 7 tests; smoke check on validation baselines only (not logged) | Offline replay instead of DB replay (Deviation log); doc 16 §5 implementation note. Existing validation runs have no predictions file: the tuned re-runs will | Noisy tuning finishes → tuned validation ablations clean + noisy, then stats + operational on them |
| 2026-11-22 | 7.3.2 (run), 7.3.5 (code) | SYN-clean tuning finished (15 cells, 300 trials, 7.8 h; logged as tuning-20261121T172441Z); tuned parameters committed in `configs/tuning/`; SYN-noisy tuning started. Statistics tool `tools/training/stats.py`: one-sided Wilcoxon per comparison and horizon, Holm across horizons, median relative MAE reduction with 10,000-resample bootstrap CI, ≥ 5 % practical flag, H6 ranking, H7 coverage CI; ablation now records peak and post-release stratum MAE per event (11 tests; scipy made an explicit dependency, already installed) | Best max_depth at the search-space upper bound (8) in 12/15 cells, kept as documented and noted in the log; CV scores are training-event scores, not results. 7.3.5 ticks when applied to the test-split runs | Tuned validation ablations (clean, noisy) after noisy tuning; 7.4 classification + lead-time code |
| 2026-11-21 | 7.3.1 runs, 7.3.2, 7.3.3 (code) | Validation ablations SYN-clean and SYN-noisy logged; Optuna tuning tool (20 trials × 3 folds, deviation logged) — SYN-clean tuning run started; split-conformal CQR (`forecasting/conformal.py`): offsets per horizon in the model manifest, applied by the online cycle, computed by `train.py`; ablation reports raw and conformal coverage/width (validation: 2-fold cross-calibration by event); doc 10 §11 implementation notes | 7.3.3 is ticked only after coverage is measured with tuned models. Postgres tests skipped (Docker off; no DB code changed) | finish tuning (clean, then noisy) → tuned validation ablation with conformal coverage |
| 2026-11-21 | 7.1.1–7.1.3, 7.2.2, 7.2.3 | Public data (Mall, SHT-B test, MOT20-01/03; MOT20 archive deleted after extraction); count MAE by band (`eval_counts`), flow error on virtual lines (`eval_flows`); noise model calibrated (`calibrate_noise` → `configs/crowdsim/noise_calibrated.yaml`); SYN-noisy for all 180 events (`make_noisy`); dataset/ablation `--data clean\|noisy` with the clean target kept | Negative result: SHT-B relative MAE 0.711. Count runs recorded the end commit (logged with justification; tools fixed). Tests needing Postgres skipped this session (Docker not running; no DB code changed) | 7.3.1 validation ablation (clean, then noisy, one at a time) |
| 2026-11-21 | 6.3.3, 6.3.4, MS3 | `tools/vision/run_camera.py` (camera YAML → pipeline → REAL observations via the ingestion API, aggregates-only summary); Shibuya demo venue/camera/event configs (illustrative halves, illustrative event time); fixed-clip regression test (first 5 s, tiled YOLOX-s, frozen aggregates). **MS3 met:** the public clip produced REAL observations end to end (2 zone-minutes, 0 rejected; logged as a demo, no ground truth) | To place polygons, one downscaled frame was viewed in the scratch folder and deleted immediately (never in the repo or DB). Untiled detection found almost nobody in the dense clip, so the regression test uses tiling | 7.1.1 |
| 2026-11-21 | 6.2.3, 6.3.1, 6.3.2 (+ 6.3.3 logic) | `aggregation/counting.py`: foot-point occupancy per region, debounced line crossings (band 10 px, one per direction per 10 s, step-back cancels), line orientation from the camera's regions, minute aggregation (median / κ, flows, LOW_CONFIDENCE / PARTIAL); `vision/pipeline.py` frames → detector → ByteTrack → rows; 13 tests incl. a privacy test (pipeline writes nothing to disk) | A test I wrote first mis-stated rule 3 (out-then-in within 10 s is a step-back, cancelled) — test corrected, code was right. Flows for zones without a region in the camera are not emitted as rows | 6.3.3 |
| 2026-11-21 | 6.2.1, 6.2.2 | 6.2.1 = existing `PersonDetector` / `YoloxOnnxDetector`; `vision/tracking.py` ByteTracker (doc 09 §5 thresholds, buffer 30 frames, unconfirmed tracks, geometry-only output with foot point); 6 tests on synthetic boxes | In-house ByteTrack (deviation logged); scipy treated as untyped in mypy | 6.3.1 |
| 2026-11-21 | 6.1.1, 6.1.2 | `vision/frames.py` FrameSource (sampled frames stamped with event time = start + i/fps, in memory only); camera YAML v1 `venue_graph/camera_config.py` (regions with κ + primary, counting lines on venue connections, checked against the venue); doc 12 → v0.4 §6.3 (contract change); 9 tests (generated clip, no people) | ByteTrack decision: implement the algorithm in-house (~150 lines, scipy assignment) instead of `supervision` (MIT, but 9 extra runtime deps incl. PyAV/matplotlib) — deviation logged with 6.2.2 | 6.2.2 |
| 2026-11-21 | accelerator check | User pointed out the NPU; iGPU (DirectML) benchmarked first: detector `device` option + `compare_devices` tool; identical detections, no meaningful speed-up for YOLOX-s + tiles → CPU stays default (logged) | NPU (Ryzen AI, needs INT8 quantisation + vendor stack) not tried: an extension, only with user go-ahead after the CPU pipeline is measured | 6.1.1 |
| 2026-11-21 | 5.3.1–5.3.4 | `forecasting/xgb.py` (3-quantile booster per horizon, inverse transform + sorted quantiles), `tools/training/{dataset,train}.py` (validation-only metrics, manifest, registry), cycle uses the active model (cold start < 15 min, family check, any failure → B0, logged), `GET/POST /api/models…/activate`; xgboost + scikit-learn added; A4 model 447 trained on clean commit `9ba4377` and activated. **Phase 5 exit met** on the hand-written example event: FC PREDICTED 18 min before CURRENT; C1/WC release spikes not anticipated (logged as a demo, n = 1) | First training run recorded a dirty tree (edits during the run) → superseded; train.py now records the commit at start and refuses dirty trees. Validation-only numbers in EXPERIMENT_LOG; h5/h15 hit the 2000-round cap; P10–P90 under-covers at 30 min (0.751) — tuning + conformal in Phase 7 | 6.1.1 |
| 2026-11-21 | 5.2.3 | V2 (10 zones) and V3 (12 zones) venue files (layouts invented from the doc 12 §5.4 descriptions, illustrative); `tools/crowdsim/generate.py` (DESIGN §9 placeholders, per-event seeds); 180 SYNTHETIC events simulated in 5.4 min (17 MB, git-ignored; every event empties); `configs/splits.json` frozen and committed BEFORE any training code: train 84 / validation 18 / test_in_venue 18 / test_new_venue 60 (seed 2027); 3 tests (disjoint, sizes, V3 held out, reproducible from the seed) | V3 needed a 12th zone to match the stated count (6 + 2 + 2 + food = 11): a facilities zone was added | 5.3.1 |
| 2026-11-21 | 5.1.1–5.1.4, 5.2.1, 5.2.2 | `forecasting/features.py`: one causal `build_features` (F_HIST, F_FLOW, F_SCHED, F_NBR; configs A1–A4, A4_NONBR), `add_target` (y = ΔN/C, tail dropped); `forecasting/sources.py` (venue info, published schedule, training-only outflow shares); 15 tests incl. TC-ML-02 for every config, 60-min online window = whole-event row at t = 59/70/200/300, tampering with the future changes nothing, realised schedule never an input | Test review caught a weak check (window compared with a shifted history, hiding a fused-filter mismatch) → fixed by a fixed-look-back filter. Two deviations logged | 5.2.3 |
| 2026-11-21 | 4.5.5, MS2 | `VenueMap` (SVG polygons from the venue file, filled by level now / +5 / +15 / +30, connections drawn, one-way dashed, hatched no-data, aria-labels + tooltips); Live layout fixed so it does not shift while queries load; alert wording built from fields in event time. **MS2 check done in the browser:** fresh synthetic event replayed at 120× with `run_predictions --follow`: zone colours changed (FC High 12:57 → Critical 13:17), persistence predictions stored, CURRENT + PREDICTED alerts opened; screenshot `reports/figures/ms2_live_page_synthetic_replay.png` | **Phase 4 exit met (MS2).** Density mode and flow-weighted edges deferred to Phase 8 (no per-edge flows in the API). At high replay speed panels refresh at different moments (alerts can lead cards by a few event-minutes); fine at real time | 5.1.1 |
| 2026-11-21 | 4.5.4 | Live page: `ZoneCard` (occupancy/capacity, ratio bar with the zone's threshold ticks, level badge, +5/+15/+30 forecast shapes, flows, stale/no-data hatching, low-confidence note) sorted by max risk score; `AlertList` (level then onset, times relative to the event clock, acknowledge/resolve with query invalidation); fallback and connection-lost banners; checked in the browser | 5-min trend arrow left out (needs history; the forecast strip shows direction instead). Per-card fallback note hidden when the page banner already says all forecasts are fallback | 4.5.5 |
| 2026-11-21 | 4.5.3 | `theme/tokens.css` (doc 15 tokens, light + dark via prefers-color-scheme, mapped into Tailwind), level language (`levels.ts`, `LevelBadge`: colour + shape + word), self-hosted Inter, query hooks (5 s / 10 s refresh, paused when hidden), app shell (event selector, status, event clock from `as_of`, data origin, hatched SYNTHETIC banner, 5-page nav), routes with placeholder pages; checked in the browser (screenshots) | Contrast computed: all level colours ≥ 3.4:1 on surfaces → marks only, text uses text tokens; light `--unknown` failed on `--bg` (2.88) → #808A9C (doc 15 updated). Fixed: event selector lost the current page; sidebar not full height | 4.5.4 |
| 2026-11-21 | 4.5.1, 4.5.2 | `frontend/`: Vite 8 + React 18.3 + TypeScript 5.9 (strict) + Tailwind 4 + TanStack Query 5 + React Router 6, ESLint 10 + Prettier; dev proxy `/api` → 127.0.0.1:8000; `tools/export_openapi.py` + `npm run gen:api` (openapi-typescript) + `src/api/client.ts` (openapi-fetch, error envelope → `ApiError`); `scripts/check.ps1` now also runs frontend format/lint/build | TypeScript pinned to 5.9: TS 7 is not yet supported by typescript-eslint (< 6.1) and openapi-typescript (^5). node_modules ≈ 175 MB (git-ignored) | 4.5.3 |
| 2026-11-21 | 4.4.1, 4.4.2 | `GET /api/crowd/current`, `/history` (1m/5m, one origin), `GET /api/predictions/{event}` + `/zones/{zone}` (joined with actuals), `GET /api/alerts/{event}` + acknowledge/resolve (409 rules, audited); repository queries; 9 API tests | Staleness in event time (replays); history never mixes origins; operator actions stamped with wall-clock time; doc 14 §6 amended (contract change); model activation deferred to Phase 5 | 4.5.1 |
| 2026-11-21 | 4.3.2, 4.3.3 | `risk/alerts.py` (pure state machine over the last 3 cycles: CURRENT immediate, PREDICTED after 2 cycles with smallest horizon, auto-resolve after 3 cycles below θH − 0.05, escalation to CRITICAL) + `risk/engine.py` (rebuilds signals from stored observations/predictions, writes alerts + audit, called by the cycle); 10 pure tests (TC-ALR-01..06, flapping, missing data, reopen) + 5 DB tests; dev event 32 re-run: 10 alerts, all auto-resolved | No pending state stored: derived from the last 3 cycles, so replays re-run identically. Missing data never resolves an alert. With B0 the PREDICTED alert follows the CURRENT one by a cycle: zero lead time, the bar learned models must beat | 4.4.1 |
| 2026-11-20 | 4.3.1, 4.2.1–4.2.3 | `risk/levels.py` (level, risk score, per-zone thresholds; TC-CNG-01..03 incl. 0.756); `forecasting/cycle.py` (event-time cycle, 60-min window, gaps ≤ 3 min forward-filled, staler zones skipped and logged, B0 fallback logged, idempotent upsert); `tools/run_predictions.py` (back-fill / `--follow`, event time taken from the data); 12 tests; dev event 32 back-filled: 422 cycles, 10,128 fallback predictions in 13.7 s | Decisions: fallback p10 = p50 = p90 (no invented spread); built-in `B0_persistence` model row, never active; synthetic events read SYNTHETIC, others REAL; MANUAL never an input. No learned model yet, so every prediction is fallback | 4.3.2 |
| 2026-11-20 | 4.1.1, 4.1.2 | `forecasting/baselines.py` B0–B3 exactly per doc 10 §2/§3.2 (vectorised over zones, forward-fill only, B3 clipped to [0, 1.5 C], B2 unclipped as specified) + 9 hand-computed tests; `forecasting/interfaces.py` | **Convention fix:** CROWDSIM switched to occupancy at the END of each bucket (doc 10 §1.1) so every value in row t is known at issue time t; doc 10 → v0.2 corrects the §3.1 conservation index (doc was internally inconsistent; B3 unchanged). Figure regenerated | 4.2.1 |
| 2026-11-20 | 3.4.3 | `tools/crowdsim/replay.py` (stdlib HTTP, adjustable speed-up, batches ≤ 1,000 rows) + end-to-end DB test; V1 run replayed into dev event 32 through the live API: 3,376 zone-minutes, 0 rejected, 2.0 s | **Phase 3 exit met.** Test isolation fix: a schema test read every observation in the table, broke once the dev DB held replayed rows | 4.1.1 |
| 2026-11-20 | 3.4.2 | `tools/crowdsim/plot.py`; figure `reports/figures/crowdsim_v1_spring_fest_day1_regimea_seed2027-0.png` (SYNTHETIC, regime A placeholders, commit 527119b) | Eye check found a design flaw, fixed: "stay until the item ends" made exhibition visitors stay 5 h → only shows hold visitors (DESIGN §7). Remaining, kept on purpose (not tuned away): food court at its jam limit through the lunch window = demand above capacity under these placeholders | 3.4.3 |
| 2026-11-20 | 3.3.1–3.3.6, 3.4.1 | CROWDSIM core (`tools/crowdsim/`: params, schedule perturbation, agent loop with logit choice, capacity queues, spillback, speed–density, exit wave; Parquet + manifest output; CLI); 13 tests incl. exact conservation (TC-GR-04) for regimes A and B, determinism, spillback, perturbation ranges; 7-h V1 event in ≈ 1–1.5 s; `pandas`, `pyarrow` (+ `pandas-stubs` dev) added | Bug found by tests and fixed: agents queued towards a jammed zone at closing time never left (gridlock) → at closing all queued agents re-route to an exit. With regime A placeholders the V1 corridor C1 reaches its jam limit (750) at peak: a real bottleneck under these illustrative parameters | 3.4.2 |
| 2026-11-20 | 3.2.1 | `tools/crowdsim/DESIGN.md` + `configs/crowdsim/regime_a.yaml` / `regime_b.yaml`: every value tagged [DOC] or [PH] placeholder; bucket convention for exact conservation; seeds from master 2027 | Interpretations recorded: pop-up 5 % per event-hour (unit unstated in doc 12); agents counted in zones, never on edges; arrivals follow the published schedule, choices the actual one | 3.3 |
| 2026-11-20 | 3.1.1, 3.1.2 | Ingestion contract: `ingestion/validation.py` (pure batch + row rules), `repository.upsert_observations` (ON CONFLICT, xmax insert/update count), `POST /api/crowd/observations`; 12 API tests (partial rejection with reasons, upsert, origin and status guards, limits) | No ADMIN (D7) → stricter SYNTHETIC/back-fill rules; future check REAL-only because replays use event time; `source` not stored — all in doc 14 §6 (contract change) | 3.2.1 |
| 2026-11-20 | 2.3.3, 2.3.4 | Read API: venue, zones (§3.6 shape), connections, graph/validate, events list (keyset cursor) + detail, schedule; `PATCH` status PLANNED→LIVE→ENDED (graph check, 409/422, audited); `storage/repository.py`, `api/schemas.py`, routers; `VenueGraph.from_connections` for DB rows; OpenAPI at `/api/docs`; 14 API tests; doc 14 → v0.2 (§6 amendments, contract change) | **Phase 2 exit met** (8 zones loaded; zones endpoint returns them; invalid graph rejected). Create endpoints not built (YAML import instead; deviation logged) | 3.1.1 |
| 2026-11-20 | 2.3.2 | `api/app.py` (`create_app`, CORS, request-id middleware, `GET /api/health`), `api/errors.py` (doc 14 §1.1 envelope for 400/404/405/409/422/500), `storage.check_database`; 8 API tests; server smoke-tested with uvicorn; `httpx` dev dependency | Health returns 503 when the DB is down (spec silent on status code). 401/403/429 omitted (D7). Starlette warns that `httpx` should become `httpx2` in its test client: works, not changed yet | 2.3.3 |
| 2026-11-20 | 2.3.1 | `storage/config_loader.py` (`load_venue`, `load_event`: validate everything, then insert in one transaction; refuse duplicates; audit_log rows) + `storage/interfaces.py`; CLI `tools/load_config.py`; 5 DB tests; V1 + example event loaded into the dev DB via the CLI | Fixed SQLAlchemy 2.1 `Result.tuples()` deprecation. Venue lookup is by name (no unique constraint on `venues.name`; loader enforces it) | 2.3.2 |
| 2026-11-20 | 2.2.2, 2.2.3 | `VenueGraph.adjacency()` (binary + width-weighted, zones only, rows = from), `shortest_path()` / `travel_time_s()` (Dijkstra on τ), `travel_time_matrix()` for CROWDSIM; 5 tests incl. TC-GR-03 (V1 matrix built by hand) | OUTSIDE allowed only as route start/end, never as a shortcut between gates. Normalised Â (GNN extension) and Π̄ (estimated from data) not built. TC-GR-04 deferred to CROWDSIM | 2.3.1 |
| 2026-11-20 | 2.2.1 | `venue_graph/graph.py`: `VenueGraph` (networkx DiGraph incl. OUTSIDE, keyed by zone code), `validate()` → ISOLATED / UNREACHABLE / NO_PATH_OUT errors + NO_COUNTING_LINE warnings, `require_valid()`; 9 tests incl. TC-GR-01/02; V1 validates clean; `networkx` added (BSD-3-Clause, named in doc 07) | Rule 3 (w, τ > 0) enforced at YAML parse. Rule 4 skipped until camera config exists (would otherwise warn on every edge). Isolated zones reported once, not also as unreachable | 2.2.2 |
| 2026-11-20 | 2.1.3 | Event + published-schedule YAML v1 (`venue_graph/event_config.py`) + 12 tests; `configs/events/v1_spring_fest_day1.yaml` (9 items; headline band from doc 13, rest `[new]`, illustrative); doc 12 → v0.3 (§6.2, contract change) | YAML only (doc allowed YAML or CSV). Rule added: items must lie inside the event window. Event + venue formats both live in M5 | 2.2.1 |
| 2026-11-20 | 2.1.2 | `configs/venues/v1.yaml`: 8 zones, 10 connections (19 directed edges) from doc 11 §6, test that it matches the doc 11 table | Docs give areas/capacities/graph and 3 polygons + 1 edge; 5 polygons and 9 widths/travel times invented and tagged `[new]` (illustrative placeholders) | 2.1.3 |
| 2026-11-20 | 2.1.1 | Venue YAML format v1 as Pydantic models (`crowdcast/venue_graph/config.py`, `interfaces.py`) + 26 tests; doc 12 → v0.2 (§6.1 format spec, contract change); `shapely` added (BSD-3-Clause) for polygon validity | Entry/exit flags derived from OUTSIDE connections; `illustrative` flag required in every venue file. GitHub contributor sidebar still showed Claude after the rewrite: API shows only prajj267, so it is GitHub's cache | 2.1.2 |
| 2026-11-20 | 1.4.3, repo | `TiledDetector` + 7 tests; benchmark `--tiled`, prints live; run bench-20261120T134304Z logged; provisional choice YOLOX-s + tiles @ 5 FPS (deviation logged). Git history rewritten to remove AI co-author trailers (messages only; IDs in logs updated) and force-pushed | MS1 reached. Model choice provisional until MOT20 accuracy (7.1); doc 09 still describes YOLO11 and no tiling (fold into 0.3.x doc updates) | 2.1.1 |
| 2026-11-20 | 1.4.2 re-run | Benchmark re-run from committed code `f78e479` (was `18f6812`) (bench-20261120T133722Z), logged; provisional run marked superseded | Speed varied 23–44 % between runs (background load); detections identical. Use repeated runs for any final speed figure | 1.4.3 |
| 2026-11-20 | repo | README rewritten for current state; first commit `0411799` (was `f1b56aa`); pushed to public GitHub repo; D3 changed to public | Benchmark run bench-20261120T133002Z predates the commit; re-run from committed code before citing | 1.4.3 |
| 2026-11-20 | 1.4.2 | `tools/vision/bench_detector.py` + tests; clip: Wikimedia Commons Shibuya Crossing (CC BY-SA 4.0, SHA-1 verified) in `videos/public/`; run bench-20261120T133002Z logged in EXPERIMENT_LOG (provisional: code uncommitted) | All three models run faster than real time at 5 FPS on CPU, but nano/tiny at 416 px find far fewer people per frame than s at 640 px on this 1080p wide shot (no ground truth, so recall not measured). Wikimedia blocked scripted download (HTTP 429); user downloaded by browser | 1.4.3 |
| 2026-11-20 | 1.4.1 | onnxruntime + numpy + opencv-python-headless; YOLOX nano/tiny/s ONNX (release 0.1.1rc0, Apache-2.0) fetched to `models/yolox/` with sizes + SHA-256 in `configs/vision/yolox_models.yaml`; `crowdcast/vision` (`PersonDetector` interface, YOLOX letterbox→decode→NMS); smoke test on YOLOX `assets/dog.jpg`; 25 tests pass + 15 db skipped (Docker off) | Found: these exports need the *raw BGR* input of the YOLOX main branch (legacy ImageNet normalisation gave no detections); inputs are fixed-size (deviation logged). Release has no checksums → trust on first use | 1.4.2 |
| 2026-11-20 | 1.2, 1.3 | uv + managed CPython 3.12.16; pyproject, ruff/mypy/pytest/pre-commit, `scripts/check.ps1`; config + time helpers; Postgres 16 in Docker; ORM models + Alembic migration v1 (upgrade/downgrade/upgrade verified); doc 13 → v0.2 and ER diagram updated for D6/D7; 29 tests pass (15 against live DB) | Fixed: `localhost` IPv6 stall (use 127.0.0.1); a `SET` before Alembic silently rolled back the migration. Nothing committed yet | 1.4.1 |
| 2026-11-20 | 0.1.1, 1.1 | D4 split demo, D5 no deadline; 1.1.1–1.1.3 (git init on `main`, .gitignore, layout, EXPERIMENT_LOG.md) | Nothing committed yet; `gh` not logged in; `uv` not installed | D8, then 1.2.1 |
| 2026-11-20 | 0.1.1 (partial) | D1 React, D2 YOLOX, D3 private GitHub, D6 public datasets only, D7 no auth | Plan extended to ≈ 50 days; Phases 1.4, 4.5, 6.2, 7.1–7.2 and 8 re-scoped; deviations logged; Node v24.15.0 / npm 11.12.1 present | Fill D4, D5, D8 |

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
| 1 | Foundations (repo, env, DB) | 1 | 3 | MS1 | In progress |
| 2 | Venue graph and configuration | 1–2 | 3 | — | Not started |
| 3 | CROWDSIM v1 and ingestion | 2 | 5 | — | Not started |
| 4 | Vertical slice (baselines, risk, React scaffold + live page) | 3 | 7 | **MS2** | Not started |
| 5 | Forecasting core (features, XGBoost) | 4 | 5 | — | Not started |
| 6 | CV pipeline on CPU | 5 | 6 | **MS3** | Not started |
| 7 | Data, experiments, evaluation | 6–7 | 9 | **MS4** | Not started |
| 8 | Dashboard completion (React) | 8–9 | 6 | — | Not started |
| 9 | Hardening, report, demo | 9–10 | 4 | **MS5** | Not started |
| X | Extensions (gated) | buffer | — | MS6 | Not started |

**Current focus:** Phase 1 (Phase 0 still open: D8 and doc updates 0.3.x)
**Next task:** 1.4.3 (choose model + sampling rate; needs decision on small-person recall)

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
| D3 | Repository visibility | Public / private | Private until the report is submitted | **Private GitHub repo**; CI with GitHub Actions | 2026-11-20 |
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
- [ ] 1.4.3 Choose the model and frame-sampling rate from the measurements; record it in the Deviation log

**Exit (MS1):** `docker compose up -d` plus `alembic upgrade head` work; `pytest` passes; CPU detector speed measured and recorded.

---

## Phase 2 — Venue graph and configuration (M5)

### 2.1 Configuration formats
- [ ] 2.1.1 Venue YAML schema (zones: code, type, area, capacity, polygon; connections: from, to, width, travel time, bidirectional), per [12 §6](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md)
- [ ] 2.1.2 `configs/venues/v1.yaml` from [11 §6](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md) (illustrative values, labelled as such)
- [ ] 2.1.3 Schedule YAML/CSV format and one example event schedule for V1

### 2.2 Venue graph module (M5)
- [ ] 2.2.1 Graph construction and the validation rules in [11 §9](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md)
- [ ] 2.2.2 Adjacency matrices and shortest-path travel times ([11 §5.3](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md))
- [ ] 2.2.3 Unit tests from [17 §2.2](DOCUMENTATION/17_TESTING_STRATEGY.md)

### 2.3 Loading and API skeleton (T2.1, T2.2, T2.5)
- [ ] 2.3.1 CLI: load venue YAML and event + schedule YAML into the database
- [ ] 2.3.2 FastAPI app with `GET /api/health` and the error envelope ([14 §1.1](DOCUMENTATION/14_API_SPECIFICATION.md))
- [ ] 2.3.3 Read endpoints: venues, zones, events; event status transitions ([14 §3.2–3.7](DOCUMENTATION/14_API_SPECIFICATION.md))
- [ ] 2.3.4 API tests for these endpoints

**Exit:** loading `v1.yaml` creates 8 zones; `GET /api/venues/{id}/zones` returns them; graph validation rejects an invalid venue.

---

## Phase 3 — CROWDSIM v1 and ingestion (T1.6, T2.3, T2.4)

### 3.1 Ingestion contract (AD-02)
- [ ] 3.1.1 `POST /api/crowd/observations` with every validation rule in [14 §3.8](DOCUMENTATION/14_API_SPECIFICATION.md): partial rejection, upsert, `data_origin` guard
- [ ] 3.1.2 Tests: valid batch, partial rejection, wrong zone, unaligned bucket, SYNTHETIC posted to a non-synthetic event

### 3.2 CROWDSIM design (T1.6)
- [ ] 3.2.1 Design note `backend/tools/crowdsim/DESIGN.md`: parameters, ranges and seeds; placeholder values clearly labelled

### 3.3 CROWDSIM core ([12 §5.1](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md))
- [ ] 3.3.1 Arrivals (non-homogeneous Poisson) and agent state; tick δ = 10 s
- [ ] 3.3.2 Destination choice (multinomial logit: attraction, distance, crowding)
- [ ] 3.3.3 Movement along shortest paths with edge capacity, queueing and spillback
- [ ] 3.3.4 Speed–density relation and departures (exit wave)
- [ ] 3.3.5 Schedule perturbation: start offset U(−5, +10) min, popularity LogNormal(0, 0.3), 5 % pop-up events
- [ ] 3.3.6 Per-minute output to Parquet (true N, flows, speed, published and actual schedule) per [12 §5.2, §6](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md)

### 3.4 Validity and replay
- [ ] 3.4.1 Unit test: venue-level conservation holds exactly ([12 §5.5](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md))
- [ ] 3.4.2 Plot occupancy profiles for one event and check them by eye; save the plot under `reports/figures/` (SYNTHETIC label on the figure)
- [ ] 3.4.3 Replay client: posts minute buckets to the ingestion API at an adjustable speed-up, with `data_origin = SYNTHETIC`

**Exit:** a 6-hour V1 event generates in seconds and its replay appears in `crowd_observations`.

---

## Phase 4 — Vertical slice (MS2)

### 4.1 Baselines ([10 §2–3](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md), T3.7)
- [ ] 4.1.1 B0 persistence, B1 moving average (k = 5), B2 linear trend (10 min), B3 conservation extrapolation
- [ ] 4.1.2 Unit tests with hand-computed values

### 4.2 Prediction cycle (T3.1, [10 §12](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md))
- [ ] 4.2.1 Cycle every 60 s of event time: read the latest observations, predict +5/+15/+30 min, write `predictions`
- [ ] 4.2.2 Falls back to B0 when no active model exists or a model fails; the fallback is logged
- [ ] 4.2.3 Works in replay mode (event time, not wall-clock time)

### 4.3 Risk engine (M7, T3.2)
- [ ] 4.3.1 Level function and risk score ([08 M7](DOCUMENTATION/08_MODULE_DESIGN.md)); per-zone thresholds
- [ ] 4.3.2 Alert state machine: CURRENT opens after 1 cycle; PREDICTED after 2 consecutive cycles; resolves after 3 cycles below threshold − 0.05; escalates to CRITICAL
- [ ] 4.3.3 Tests from [17 §2.3](DOCUMENTATION/17_TESTING_STRATEGY.md), including flapping input

### 4.4 Read API
- [ ] 4.4.1 `GET /api/crowd/current/{event_id}`, `/api/crowd/history/{event_id}`
- [ ] 4.4.2 `GET /api/predictions/{event_id}` (and per zone), `GET /api/alerts/{event_id}`, acknowledge/resolve

### 4.5 React scaffold and minimal live page (D1 = React)
- [ ] 4.5.1 Scaffold `frontend/` with Vite + React 18 + TypeScript, Tailwind, TanStack Query, React Router; ESLint + Prettier; `npm run build` and `npm run lint` pass
- [ ] 4.5.2 Typed API client generated from FastAPI's OpenAPI schema (e.g. openapi-typescript), with a regeneration script; Vite dev proxy to the API
- [ ] 4.5.3 Design tokens from [15 §2.1](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md) (level colours + icons, per [11 §4](DOCUMENTATION/11_SPATIAL_INTELLIGENCE.md)) and the app shell (layout, navigation, event selector)
- [ ] 4.5.4 Live page: ZoneCards (occupancy, ratio, level) and AlertList, polling with TanStack Query
- [ ] 4.5.5 VenueMap: SVG floor plan from zone polygons in the venue YAML, filled by level

**Exit (MS2):** replaying a synthetic event changes zone colours every minute; persistence predictions are stored; a surge opens a CURRENT alert.

---

## Phase 5 — Forecasting core (T3.6, T3.8)

### 5.1 Feature builder ([10 §5](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md))
- [ ] 5.1.1 One shared `FeatureBuilder` used by both training and the online cycle
- [ ] 5.1.2 F_HIST, F_FLOW, F_SCHED (published schedule only), F_NBR (graph-derived)
- [ ] 5.1.3 Feature-set configs A1, A2, A3, A4, A4\NBR
- [ ] 5.1.4 Target y = (N(t+h) − N(t)) / C, drop rows with t + h > T; forward-fill only ([10 §6–7](DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md))

### 5.2 Leakage protection
- [ ] 5.2.1 TC-ML-02: features from a truncated series equal features from the full series up to t
- [ ] 5.2.2 Test that the actual (realised) schedule never reaches the features
- [ ] 5.2.3 Splits by event only; a test fails if one event appears in two splits

### 5.3 XGBoost and registry
- [ ] 5.3.1 XGBoost quantile regression (P10/P50/P90), direct multi-horizon; sort quantiles after the inverse transform
- [ ] 5.3.2 Training CLI: build dataset → train → write a manifest (config, data hash, seed, git commit) → register in `model_versions`
- [ ] 5.3.3 `POST /api/models/{id}/activate`; the online cycle uses the active model, with fallback to B0
- [ ] 5.3.4 PREDICTED alerts driven by model forecasts

**Exit:** an XGBoost A4 model trained on a few V1 events is active; a scripted surge raises a PREDICTED alert before the CURRENT alert.

---

## Phase 6 — CV pipeline on CPU (M1–M3, T2.7, T3.4)

### 6.1 Video input (M1)
- [ ] 6.1.1 `FrameSource` for video files with configurable frame sampling and a configured start time (event time, not wall-clock)
- [ ] 6.1.2 Camera YAML: source file, start offset, regions (polygons per zone), counting lines

### 6.2 Detection and tracking (M2)
- [ ] 6.2.1 `Detector` interface wrapping YOLOX (ONNX Runtime, CPU); person class only
- [ ] 6.2.2 ByteTrack behind a `Tracker` interface, from a permissively licensed implementation (verify its licence before adding the dependency); motion-only, no appearance features
- [ ] 6.2.3 Privacy check: no frames, crops or tracks written to disk; only aggregates

### 6.3 Counting and aggregation (M3, [09 §6](DOCUMENTATION/09_COMPUTER_VISION_METHODOLOGY.md))
- [ ] 6.3.1 Occupancy per frame (foot point inside the polygon)
- [ ] 6.3.2 Line crossings with direction and debounce
- [ ] 6.3.3 Minute aggregation with quality flags; posts REAL observations to the ingestion API
- [ ] 6.3.4 Geometry and aggregation unit tests ([17 §2.1](DOCUMENTATION/17_TESTING_STRATEGY.md)); one fixed-clip regression test

**Exit (MS3):** a recorded clip produces REAL observations end to end, together with Phase 5 complete.

---

## Phase 7 — Data, experiments and evaluation (MS4)

### 7.1 Public data and CV evaluation
- [ ] 7.1.1 Download Mall, ShanghaiTech B (test split) and 2 MOT20 sequences; check disk space first; keep them outside git
- [ ] 7.1.2 Count MAE by density band ([16 §2.1](DOCUMENTATION/16_MODEL_EVALUATION.md)); MOT20 tracking sanity check
- [ ] 7.1.3 Flow error (O2): draw virtual counting lines on MOT20 scenes and compare detected crossings with crossings derived from the annotated ground-truth tracks (if feasible; otherwise log it as a deviation)

### 7.2 Synthetic datasets
- [ ] 7.2.1 CROWDSIM v2: V2 and V3 topologies (T4.1)
- [ ] 7.2.2 Noise model ([12 §5.3](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md)): occupancy parameters (m₀, m₁, σ_r) calibrated from count errors on public datasets (7.1.2); crossing parameters (p_det, r_fp) from 7.1.3 if it was feasible. Anything uncalibrated stays a labelled placeholder
- [ ] 7.2.3 Generate SYN-clean and SYN-noisy (volume per [experimental_design §2](RESEARCH/experimental_design.md), or a documented reduction)
- [ ] 7.2.4 **Freeze `splits.json` (seed 2027) and commit it before any training run**

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

- [ ] 8.1 Prediction view: Recharts forecast chart with the P10–P90 band and a horizon selector ([15 Page 5](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md))
- [ ] 8.2 Alerts view: list, acknowledge and resolve ([15 Page 7](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md))
- [ ] 8.3 History view with CSV export ([15 Page 6](DOCUMENTATION/15_FRONTEND_SPECIFICATION.md))
- [ ] 8.4 Event and venue view (read-only, YAML import)
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
| 2026-11-20 | 1.4.2 | `tools/vision/bench_detector.py` + tests; clip: Wikimedia Commons Shibuya Crossing (CC BY-SA 4.0, SHA-1 verified) in `videos/public/`; run bench-20261120T133002Z logged in EXPERIMENT_LOG (provisional: code uncommitted) | All three models run faster than real time at 5 FPS on CPU, but nano/tiny at 416 px find far fewer people per frame than s at 640 px on this 1080p wide shot (no ground truth, so recall not measured). Wikimedia blocked scripted download (HTTP 429); user downloaded by browser | 1.4.3 |
| 2026-11-20 | 1.4.1 | onnxruntime + numpy + opencv-python-headless; YOLOX nano/tiny/s ONNX (release 0.1.1rc0, Apache-2.0) fetched to `models/yolox/` with sizes + SHA-256 in `configs/vision/yolox_models.yaml`; `crowdcast/vision` (`PersonDetector` interface, YOLOX letterbox→decode→NMS); smoke test on YOLOX `assets/dog.jpg`; 25 tests pass + 15 db skipped (Docker off) | Found: these exports need the *raw BGR* input of the YOLOX main branch (legacy ImageNet normalisation gave no detections); inputs are fixed-size (deviation logged). Release has no checksums → trust on first use | 1.4.2 |
| 2026-11-20 | 1.2, 1.3 | uv + managed CPython 3.12.16; pyproject, ruff/mypy/pytest/pre-commit, `scripts/check.ps1`; config + time helpers; Postgres 16 in Docker; ORM models + Alembic migration v1 (upgrade/downgrade/upgrade verified); doc 13 → v0.2 and ER diagram updated for D6/D7; 29 tests pass (15 against live DB) | Fixed: `localhost` IPv6 stall (use 127.0.0.1); a `SET` before Alembic silently rolled back the migration. Nothing committed yet | 1.4.1 |
| 2026-11-20 | 0.1.1, 1.1 | D4 split demo, D5 no deadline; 1.1.1–1.1.3 (git init on `main`, .gitignore, layout, EXPERIMENT_LOG.md) | Nothing committed yet; `gh` not logged in; `uv` not installed | D8, then 1.2.1 |
| 2026-11-20 | 0.1.1 (partial) | D1 React, D2 YOLOX, D3 private GitHub, D6 public datasets only, D7 no auth | Plan extended to ≈ 50 days; Phases 1.4, 4.5, 6.2, 7.1–7.2 and 8 re-scoped; deviations logged; Node v24.15.0 / npm 11.12.1 present | Fill D4, D5, D8 |

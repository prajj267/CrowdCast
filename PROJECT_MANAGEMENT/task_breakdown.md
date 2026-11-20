# Task Breakdown

Owner roles: **CV** = computer-vision lead, **ML** = ML/forecasting lead, **BE** = backend & data lead, **FE** = frontend & integration lead ([team_responsibilities.md](team_responsibilities.md)). Estimates in ideal person-days (pd). Capacity ≈ 4 people × 8 weeks × ~4 effective days/week ≈ 128 pd. Core work ≈ 108 pd (+4 pd LSTM) leaves ≈ 16 pd (≈ 12 %) contingency — tight but feasible.

## WP1 — Foundations (MS1)

| ID | Task | Owner | Est. | Depends | Req. |
|---|---|---|---|---|---|
| T1.1 | Repository layout, pre-commit (ruff, mypy, eslint), CI workflow | BE | 1.5 | — | NFR-MNT-01 |
| T1.2 | Docker Compose (postgres, api, scheduler, frontend) | BE | 1.5 | T1.1 | NFR-PORT-01 |
| T1.3 | SQLAlchemy models + Alembic migration v1 (all tables in [13](../DOCUMENTATION/13_DATABASE_DESIGN.md)) | BE | 3 | T1.1 | NFR-MNT-03 |
| T1.4 | Auth: login, JWT, refresh cookie, Argon2id, RBAC dependency | BE | 2.5 | T1.3 | FR-AUTH-01…03 |
| T1.5 | Frontend scaffold, routing, theme tokens, API client generation | FE | 2 | T1.1 | FR-DSH-01 |
| T1.6 | CROWDSIM design note + parameter ranges | ML | 1.5 | — | — |
| T1.7 | Ethics/recording approval application, consent form | CV | 1.5 | — | NFR-PRV |
| T1.8 | CV environment (CUDA, PyTorch, Ultralytics) on GPU machine | CV | 1 | — | — |

## WP2 — Configuration & ingestion (MS2)

| ID | Task | Owner | Est. | Depends | Req. |
|---|---|---|---|---|---|
| T2.1 | Venue, zone, connection CRUD + graph validation (M5) | BE | 3 | T1.3 | FR-VEN, FR-ZON |
| T2.2 | Event, schedule, operator endpoints + status transitions | BE | 2.5 | T1.3 | FR-EVT |
| T2.3 | Observation ingestion endpoint (validation, upsert, partial reject) | BE | 2 | T1.3 | FR-OBS-01…03 |
| T2.4 | CROWDSIM v1: agents, choice model, edge capacity, V1 topology, replay client | ML | 5 | T1.6, T2.3 | — |
| T2.5 | YAML loaders for venue/event (CLI) | BE | 1 | T2.1 | — |
| T2.6 | Login + event list pages | FE | 2.5 | T1.5, T1.4 | FR-DSH-01/02 |
| T2.7 | YOLO11 + ByteTrack on sample clip; FrameSource (M1) | CV | 3 | T1.8 | FR-VID-02, FR-CV-01/02 |

## WP3 — Vertical slice & prediction core (MS2–MS3)

| ID | Task | Owner | Est. | Depends | Req. |
|---|---|---|---|---|---|
| T3.1 | Scheduler process + persistence cycle + fallback | ML | 2 | T2.3 | FR-FC-01/04 |
| T3.2 | M7 levels, risk score, alert state machine + tests | BE | 3 | T3.1 | FR-CNG, FR-ALR |
| T3.3 | Live monitoring page v1 (VenueMap, ZoneCards, AlertList) | FE | 5 | T2.6 | FR-DSH-04 |
| T3.4 | Region/line geometry, debounce, M3 aggregation, posting | CV | 5 | T2.7, T2.3 | FR-CV-03/04, FR-OBS |
| T3.5 | Camera config endpoints + region/line editor on snapshot | FE + BE | 3 | T2.1 | FR-VID-03 |
| T3.6 | FeatureBuilder F_HIST/F_FLOW/F_SCHED/F_NBR + leakage tests | ML | 5 | T2.4 | FR-FC |
| T3.7 | Baselines B0–B3 | ML | 1.5 | T3.6 | — |
| T3.8 | XGBoost quantile training CLI, registry, manifest, activation endpoint | ML | 4 | T3.6 | FR-FC-02/03/05/06 |
| T3.9 | Venue configuration page (polygon editor, connections) | FE | 4 | T2.1 | FR-DSH-03 |
| T3.10 | Prediction dashboard (ForecastChart, horizon selector, table) | FE | 4 | T3.8 | FR-DSH-05 |

## WP4 — Data collection & evaluation (MS3–MS4)

| ID | Task | Owner | Est. | Depends | Req. |
|---|---|---|---|---|---|
| T4.1 | CROWDSIM v2: V2/V3 topologies, schedule perturbation, noise model | ML | 3 | T2.4 | — |
| T4.2 | Staged recording session (logistics, geometry measurement) | CV (+ all) | 2 | T1.7 | — |
| T4.3 | Annotation (≥ 300 frames, ≥ 60 min crossings), double-annotation QC | CV + FE | 5 | T4.2 | O1/O2 |
| T4.4 | CV evaluation (density bands, flow error, MOT20 check) | CV | 3 | T4.3, T3.4 | O1/O2 |
| T4.5 | Calibrate noise model from measured CV errors | ML + CV | 1 | T4.4, T4.1 | RQ5 |
| T4.6 | Ablation runner A1–A4, statistics, report tables | ML | 5 | T3.8, T4.1 | O8 |
| T4.7 | Operational replay evaluation (lead time, false alarms, misses) | ML + BE | 2 | T3.2, T4.6 | O6 |
| T4.8 | History and alerts pages, CSV export | FE | 4 | T3.10 | FR-DSH-06/07 |
| T4.9 | LSTM model (gated) | ML | 4 | T4.6 | — |

## WP5 — Hardening & delivery (MS5)

| ID | Task | Owner | Est. | Depends | Req. |
|---|---|---|---|---|---|
| T5.1 | Playwright E2E suite (TC-E2E-01…06) | FE | 3 | WP3 | — |
| T5.2 | Locust + cycle benchmarks; fix bottlenecks | BE | 2 | WP3 | NFR-PERF |
| T5.3 | Security review (role matrix, throttling, audit, dependency audit) | BE | 1.5 | WP3 | NFR-SEC |
| T5.4 | Retention jobs (data, video) | BE | 1 | T1.3 | NFR-PRV-03 |
| T5.5 | Documentation update with real results; report writing | All | 4 | WP4 | — |
| T5.6 | Demo script, rehearsal, recorded demo video | FE | 1.5 | all | — |

## Effort summary

| WP | Core pd |
|---|---|
| WP1 | 14.5 |
| WP2 | 19 |
| WP3 | 36.5 |
| WP4 (excluding T4.9) | 25 |
| WP5 | 13 |
| **Total core** | **108** |
| LSTM (gated) | 4 |
| Contingency | ≈ 16 |

## Critical path

T1.3 → T2.3 → T2.4 → T3.6 → T3.8 → T4.6 → T4.7 → T5.5. Any slip in CROWDSIM (T2.4) or the feature builder (T3.6) delays the research results directly; these get priority in stand-ups.

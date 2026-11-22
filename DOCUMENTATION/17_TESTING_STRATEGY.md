# 17 — Testing Strategy

| Field | Value |
|---|---|
| Version | 0.2 (**§5 lists what is actually tested and wins over §1–§4**) |
| Tools | pytest, pytest-cov, httpx (FastAPI TestClient), Hypothesis, testcontainers-postgres, Vitest, React Testing Library, Playwright, Locust |

---

## 1. Test levels

| Level | Scope | Tooling | Runs |
|---|---|---|---|
| Unit | Pure functions in M3, M5, M6, M7; CV geometry; React components | pytest, Hypothesis, Vitest | Every commit (CI) |
| Integration | Module + real PostgreSQL (container) | pytest + testcontainers | Every commit |
| API | All endpoints, roles, validation, errors | pytest + httpx | Every commit |
| CV | Detector/tracker/geometry on fixed clips with known answers | pytest (marked `cv`, GPU optional) | Nightly / before release |
| ML pipeline | Feature correctness, leakage, reproducibility, model contracts | pytest | Every commit (small data); full on demand |
| Frontend | Components, hooks, pages with mocked API | Vitest + RTL + MSW | Every commit |
| Performance | Prediction cycle, API latency, CV throughput | pytest-benchmark, Locust | Weekly from week 5 |
| End-to-end | Simulator → API → scheduler → dashboard | Playwright + docker compose | Before each milestone demo |

CI: GitHub Actions (free tier) running lint, type checks, unit, integration and API tests; CV and performance tests run locally on the GPU machine.

## 2. Representative test cases

### 2.1 Unit — geometry and aggregation (M2/M3)

| ID | Test | Expected outcome |
|---|---|---|
| TC-CV-01 | Foot point inside/outside/on-edge of polygon | Inside → counted; on-edge counted once (half-open rule) |
| TC-CV-02 | Synthetic track crossing a line left→right | One crossing, correct direction |
| TC-CV-03 | Track jittering ±5 px around the line for 20 frames | Zero crossings (band debounce) |
| TC-CV-04 | Track crosses, returns within 5 s | Net zero crossings (cancel rule) |
| TC-CV-05 | Two cameras see the same zone; only primary used | Occupancy equals primary count |
| TC-CV-06 | Coverage fraction 0.5, median count 100 | Occupancy 200, raw 100 |
| TC-OBS-01 | Minute bucket with 300 frames, counts [10..20] | Median used; quality OK |
| TC-OBS-02 | Bucket with 40 % frames received | quality PARTIAL |
| TC-OBS-03 | No frames | quality MISSING, occupancy null |

### 2.2 Unit — venue graph (M5)

| ID | Test | Expected |
|---|---|---|
| TC-GR-01 | Graph with isolated zone | `validate()` returns ISOLATED issue |
| TC-GR-02 | Zone not reachable from outside | UNREACHABLE issue |
| TC-GR-03 | Adjacency matrix for V1 | Matches hand-built matrix |
| TC-GR-04 | Venue-level conservation on simulator output (property test) | $\sum_i \Delta N_i$ = entries − exits exactly |

### 2.3 Unit — risk engine (M7)

| ID | Test | Expected |
|---|---|---|
| TC-CNG-01 | $u$ = 0.599, 0.600, 0.799, 0.800, 0.949, 0.950 | NORMAL, ELEVATED, ELEVATED, HIGH, HIGH, CRITICAL |
| TC-CNG-02 | Zone with overridden thresholds | Overrides applied |
| TC-CNG-03 | Risk score formula on hand-computed cases (e.g. $\hat u^{50}=0.836$, $\hat u^{90}=0.94$ → 0.756) | Matches to 1e-3 |
| TC-ALR-01 | Predicted HIGH for 1 cycle then NORMAL | No alert |
| TC-ALR-02 | Predicted HIGH for 2 consecutive cycles | One PREDICTED alert, smallest horizon recorded |
| TC-ALR-03 | Current HIGH | CURRENT alert opens immediately |
| TC-ALR-04 | $u$ oscillating 0.79/0.81 for 20 cycles | ≤ 1 alert (hysteresis) |
| TC-ALR-05 | Open alert, level rises to CRITICAL | Same alert escalated; audit logged |
| TC-ALR-06 | Below threshold − 0.05 for 3 cycles | Auto-resolved |

### 2.4 ML pipeline (M6/T2)

| ID | Test | Expected |
|---|---|---|
| TC-ML-01 | Feature builder on hand-made 3-zone series | Exact values for lags, rolling stats, schedule and neighbour features |
| TC-ML-02 | **Leakage test:** features at $t$ computed on series truncated at $t$ vs full series | Identical |
| TC-ML-03 | Splits | No event ID appears in two splits |
| TC-ML-04 | Online vs offline features | Same `FeatureBuilder` output for the same inputs (no train/serve skew) |
| TC-ML-05 | Quantile ordering | P10 ≤ P50 ≤ P90, all ≥ 0, for 10⁴ random inputs |
| TC-ML-06 | Reproducibility | Same config + seed → identical metrics (FR-FC-06) |
| TC-ML-07 | Fallback | Model file missing → persistence predictions, `is_fallback=true` |
| TC-ML-08 | Baselines on constant series | B0–B3 predict the constant |
| TC-ML-09 | Sanity on synthetic: XGB A1 vs B0 on a small dataset | Test asserts the pipeline *runs and reports both*, not that XGB wins |

### 2.5 API

| ID | Test | Expected |
|---|---|---|
| TC-API-01 | Role × endpoint matrix | Codes per [14 §2](14_API_SPECIFICATION.md) |
| TC-API-02 | Operator requests unassigned event | 404 |
| TC-API-03 | Event with `end_time < start_time` | 422 with field detail |
| TC-API-04 | Observation batch with 1 invalid row of 3 | 200, `inserted: 2`, 1 rejected with reason |
| TC-API-05 | Duplicate observation (same key) | Upsert updates row; no duplicate |
| TC-API-06 | SYNTHETIC rows into a real event by SERVICE | Rejected |
| TC-API-07 | Camera GET never contains URI | Field absent |
| TC-API-08 | Login throttling | 6th failed attempt → 429 |
| TC-API-09 | Status transition ENDED → LIVE | 409 |

### 2.6 CV (fixed clips)

| ID | Test | Expected |
|---|---|---|
| TC-CV-10 | 60-s staged clip with 12 known crossings | Crossings within ±1 |
| TC-CV-11 | Mall frames 1–200 | MAE recorded vs stored reference value of the chosen configuration (regression guard, not a target) |
| TC-CV-12 | Camera stream killed mid-run | Other streams continue; M3 marks PARTIAL/MISSING |

### 2.7 Frontend

| ID | Test | Expected |
|---|---|---|
| TC-FE-01 | `LevelBadge` renders icon + text for each level | Accessible name contains level |
| TC-FE-02 | `ZoneCard` stale data (> 3 min) | Stale indicator shown |
| TC-FE-03 | Horizon selector changes map fill source | Map uses predicted level at chosen horizon |
| TC-FE-04 | Synthetic event | Banner visible on all event pages |
| TC-FE-05 | Acknowledge button | Calls API, optimistic update, rollback on error |

### 2.8 Performance

| ID | Test | Target (from NFRs) |
|---|---|---|
| TC-PERF-01 | Prediction cycle, 15 zones | ≤ 5 s (NFR-PERF-01) |
| TC-PERF-02 | Locust, 20 users, read endpoints | p95 ≤ 300 ms (NFR-PERF-02) |
| TC-PERF-03 | 2 streams, `yolo11n`, 640 px | ≥ 5 FPS each (NFR-PERF-03) |
| TC-PERF-04 | Ingest 500-row batch | < 2 s (FR-OBS-03) |

### 2.9 End-to-end

| ID | Scenario | Expected |
|---|---|---|
| TC-E2E-01 | Organiser creates venue, zones, connections, event, schedule; goes LIVE | All visible in UI; graph valid |
| TC-E2E-02 | CROWDSIM replays a synthetic event in real time | Map updates each minute; freshness ≤ 20 s (NFR-PERF-04) |
| TC-E2E-03 | Scripted surge in C1 at minute 40 | PREDICTED alert visible ≤ 15 s after cycle (FR-ALR-05), before CURRENT alert |
| TC-E2E-04 | Operator acknowledges and resolves | Status and audit trail correct |
| TC-E2E-05 | Backend container restarted mid-event | No data lost; dashboard recovers |
| TC-E2E-06 | Recorded video replay through CV worker | Observations with origin REAL appear |

## 3. Test data

- `tests/fixtures/venues/v1.yaml` (8-zone reference), short synthetic events (30 min, seed fixed), 2–3 short annotated clips from the staged scenario (consented), Mall subset (if licence allows redistribution inside a private repo; otherwise downloaded by script).
- No real-person video committed to a public repository.

## 4. Definition of done (per feature)

Code reviewed by another team member; unit tests added; CI green; requirement IDs referenced in PR description; docs updated if a contract changed.

## 5. Solo implementation and traceability (v0.2, 9.4 audit)

Where this section and §1–§4 differ, this section wins. The solo definition of done is in `CLAUDE.md §8` (ruff, mypy and pytest pass; tests cover the new logic; no code review by a second person).

### 5.1 Tooling as built

| Topic | Planned (§1, §3) | Implemented |
|---|---|---|
| Unit, integration, API | pytest, httpx, testcontainers | pytest with FastAPI `TestClient`. Tests marked `db` run against the Docker PostgreSQL inside a rolled-back transaction and are **skipped** when it is down (no testcontainers). Hypothesis (property testing) is not used |
| CV tests | Fixed clips, GPU optional | `test_cv_regression.py` (marker `model`, skipped without `models/yolox/`): first 5 s of the public Shibuya clip, CPU. Accuracy is measured by the Phase 7 evaluation runs in `EXPERIMENT_LOG.md`, not by tests |
| Frontend | Vitest + RTL + MSW | Vitest + Testing Library with a mocked API client (no MSW) |
| Performance | pytest-benchmark, Locust | `tools.bench_cycle` (prediction cycle) and `tools.vision.bench_detector` (detector), each a logged run. No Locust, no pytest-benchmark |
| End-to-end | Playwright + docker compose | `tools.smoke_e2e`: migrations → config → CROWDSIM → replay through the API → predictions → alerts on a throwaway database, checked through the API. No browser automation |
| CI | GitHub Actions: lint, types, unit, integration, API | `.github/workflows/ci.yml`: ruff, mypy, full pytest with a PostgreSQL 16 service, OpenAPI client drift, frontend format/lint/build/Vitest, privacy check. Tests needing model files or videos are skipped there |
| Test data (§3) | Fixture YAML, staged clips (consented), Mall subset | Committed venue/event YAML in `configs/`; synthetic series built inside the tests. No staged clips (D6: public datasets only). No dataset or video is committed |

### 5.2 Test-case traceability

Status: **Named**: a test carries the ID in its name or description. **Covered**: a test checks the same behaviour under another name. **Partial**: only part of the expected result is checked. **Tool**: checked by a logged tool run, not a test. **Not built**: the feature is out of solo scope. **Open**: not tested. Backend tests are in `backend/tests/`, frontend tests in `frontend/src/`.

| ID | Status | Where | Note |
|---|---|---|---|
| TC-CV-01 | Partial | `test_counting.py::test_foot_points_counted_per_region` | Inside/outside checked; the on-edge case is not |
| TC-CV-02 | Covered | `test_counting.py::test_crossing_counts_in_and_out_with_direction` | |
| TC-CV-03 | Covered | `test_counting.py::test_jitter_inside_the_band_is_not_a_crossing` | |
| TC-CV-04 | Covered | `test_counting.py::test_stepping_back_within_10_s_cancels` (+ 3 related tests) | Cancel window is 10 s as in [09 §6.2](09_COMPUTER_VISION_METHODOLOGY.md), not 5 s |
| TC-CV-05 | Not built | — | One camera per run; no fusion across cameras |
| TC-CV-06 | Covered | `test_counting.py::test_minute_median_coverage_and_quality` | Coverage 0.5: raw 3 → occupancy 6 |
| TC-OBS-01 | Covered | same test | Median of the minute, quality OK |
| TC-OBS-02 | Covered | same test | Quality PARTIAL |
| TC-OBS-03 | Partial | `test_api_ingestion.py::test_missing_quality_allows_null_occupancy` | The aggregator posts no row for a minute without frames; the API accepts MISSING with null occupancy |
| TC-GR-01 to 03 | Named | `test_venue_graph.py::test_tc_gr_0*` | |
| TC-GR-04 | Covered | `test_crowdsim.py::test_conservation_holds_exactly` | Exact check on simulator runs, not a Hypothesis property test |
| TC-CNG-01 to 03 | Named | `test_risk_levels.py::test_tc_cng_0*` | |
| TC-ALR-01 to 06 | Named | `test_risk_alerts.py::test_tc_alr_0*` | Also `test_risk_engine.py` against the database |
| TC-ML-01 | Partial | `test_features.py` (schedule values, target) | Hand values for schedule features and the target; no single hand-made 3-zone check of every group |
| TC-ML-02 | Named | `test_features.py::test_tc_ml_02_truncated_series_gives_same_features` | Also `test_changing_the_future_does_not_change_features`, `test_actual_schedule_never_reaches_features` |
| TC-ML-03 | Covered | `test_splits.py` | Committed `splits.json` disjoint; overlap rejected |
| TC-ML-04 | Covered | `test_features.py::test_online_60_minute_window_equals_the_whole_event` | Training and the cycle call the same `FeatureBuilder` |
| TC-ML-05 | Partial | `test_xgb.py::test_inverse_transform_floors_at_zero_and_sorts_quantiles`, `::test_quantile_model_orders_quantiles_and_round_trips` | Ordering and non-negativity checked on fixed inputs, not 10⁴ random ones |
| TC-ML-06 | Partial | `test_crowdsim.py::test_same_seed_same_output`, `test_splits.py::test_split_is_reproducible_from_the_seed` | Data and splits are reproducible; repeated training runs are not compared by a test |
| TC-ML-07 | Covered | `test_model_activation.py::test_cold_start_falls_back_to_persistence`, `::test_broken_model_falls_back_and_logs`; `test_xgb.py::test_missing_artifacts_are_reported` | |
| TC-ML-08 | Partial | `test_baselines.py` | B0–B3 checked on hand-made series, not specifically on a constant one |
| TC-ML-09 | Partial | `test_ablation.py` | Checks that baselines and per-event metrics are computed; XGB vs B0 is compared in the logged ablation runs |
| TC-API-01, 02, 08 | Not built | — | No roles, assignments or login (D7) |
| TC-API-03 | Covered | `test_event_config.py::test_event_window_rules` | Events come from YAML ([12 §6](12_DATASET_AND_DATA_COLLECTION.md)); the config loader rejects the file instead of an API 422. The database also has a CHECK constraint |
| TC-API-04 | Covered | `test_api_ingestion.py::test_partial_rejection_keeps_valid_rows` | |
| TC-API-05 | Covered | `test_api_ingestion.py::test_same_key_again_is_an_update` | |
| TC-API-06 | Covered | `test_api_ingestion.py::test_synthetic_into_real_event_is_refused` | |
| TC-API-07 | Not built | — | No camera endpoints ([14 §6](14_API_SPECIFICATION.md)) |
| TC-API-09 | Covered | `test_api_venues_events.py::test_invalid_transition_is_409` | |
| TC-CV-10 | Not built | — | No staged clip (D6). Crossing accuracy is measured on MOT20 instead (EXPERIMENT_LOG run `flows_20261121T145720Z`) |
| TC-CV-11 | Covered | `test_cv_regression.py` | Regression guard on the Shibuya clip instead of Mall frames |
| TC-CV-12 | Not built | — | Offline, one clip per run; no live streams |
| TC-FE-01 to 05 | Named | `components.test.tsx`, `live.test.tsx`, `Shell.test.tsx`, `mutations.test.tsx` | |
| TC-PERF-01 | Tool | `tools.bench_cycle` | Logged in `EXPERIMENT_LOG.md` (WORKFLOW 9.2) |
| TC-PERF-02 | Open | — | No API load test |
| TC-PERF-03 | Tool | `tools.vision.bench_detector` | YOLOX instead of `yolo11n` (D2); CV runs offline, so 5 FPS is the sampling rate, not a real-time target. Logged in `EXPERIMENT_LOG.md` |
| TC-PERF-04 | Open | — | Batch limits are tested (`test_batch_size_limits`), ingest time is not |
| TC-E2E-01 | Not built | — | Configuration is YAML, not the UI |
| TC-E2E-02, 03 | Partial | `tools.smoke_e2e` | Replay → predictions at 5/15/30 min → alerts, checked through the API; no browser, no freshness or latency timing, no scripted surge |
| TC-E2E-04 | Partial | `test_api_dashboard_reads.py`, `frontend/src/hooks/mutations.test.tsx` | Acknowledge/resolve tested at API and component level; `smoke_e2e` checks auto-resolve only |
| TC-E2E-05 | Open | — | Restart recovery not tested |
| TC-E2E-06 | Tool | `tools.vision.run_camera` | One logged demonstration run on a public clip (EXPERIMENT_LOG `cv-SHIBUYA1-20261120T234449Z`); not automated |

## 6. Change log

| Version | Date | Change |
|---|---|---|
| 0.2 | 2026-11-23 | §5 added (9.4 audit, F-17): tooling as built, traceability of every test-case ID |
| 0.1 | — | Team plan |

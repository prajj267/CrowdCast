# 17 — Testing Strategy

| Field | Value |
|---|---|
| Version | 0.1 |
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

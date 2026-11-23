# 02 — Objectives and Scope

| Field | Value |
|---|---|
| Version | 0.2 |
| Status | Design baseline (§1–§6) with the **solo scope in §7, which wins where they differ** |

---

## 1. Aim

Build and evaluate a working prototype that estimates zone-level crowd occupancy from recorded or simulated event footage, forecasts occupancy 5, 15 and 30 minutes ahead, and warns operators of zones likely to become congested — and use it to test whether event-schedule and neighbouring-zone information improve forecasts over independent zone-wise models.

## 2. Objectives

Each objective is measurable and traced to requirements ([06](06_REQUIREMENTS_SPECIFICATION.md)) and evaluation ([16](16_MODEL_EVALUATION.md)).

| ID | Objective | Success measure (target, not a result) | Requirements |
|---|---|---|---|
| O1 | Estimate current occupancy per zone from video | Count MAE reported per density band on ≥ 300 manually annotated frames from our own footage | FR-CV-01…05 |
| O2 | Measure zone inflow/outflow across boundaries | Line-crossing count error reported per 5-min window on ≥ 60 min of annotated footage | FR-CV-04 |
| O3 | Store a per-minute occupancy time series per zone | 100 % of 1-min buckets present or explicitly flagged missing | FR-OBS-01…04 |
| O4 | Forecast $N_i(t+h)$ for $h \in \{5,15,30\}$ | Recommended model beats persistence baseline (lower MAE) on held-out events at each horizon, or the failure is reported | FR-FC-01…06 |
| O5 | Classify predicted congestion levels | Precision, recall, F1 reported for the HIGH-or-above class at each horizon | FR-CNG-01…03 |
| O6 | Generate early warnings | Median warning lead time, false-alarm rate and missed-episode rate reported on held-out events | FR-ALR-01…05 |
| O7 | Visualise current and predicted state | Operator can identify the most at-risk zone within 10 s in a usability walkthrough (5 participants) | FR-DSH-01…08 |
| O8 | Answer the research questions via ablation | Ablations A1–A5 run on identical splits with significance tests | [experimental_design.md](../RESEARCH/experimental_design.md) |

## 3. Scope

### 3.1 Core scope (must be delivered in the 8-week prototype)

| Area | Included |
|---|---|
| Configuration | Venues, zones (with area and planning capacity), zone connections, events, schedule items, cameras, camera regions and counting lines |
| Vision | Offline/near-real-time processing of **recorded** video files with YOLO-family person detection, ByteTrack tracking, polygon occupancy counts and line-crossing flows |
| Data | Per-minute observations per zone; synthetic data generator (CROWDSIM); manual annotation tool workflow (spreadsheet/CSV import) |
| Forecasting | Persistence, moving average, conservation-extrapolation baselines; XGBoost (direct multi-horizon, quantile outputs) |
| Risk | Rule-based congestion levels from predicted occupancy ratio; alert lifecycle with hysteresis |
| API | REST API (FastAPI) with JWT authentication and role-based access |
| Dashboard | Login, event management, venue configuration, live monitoring, prediction view, history, alerts |
| Evaluation | CV, forecasting, classification and operational metrics; ablation A1–A4 |

### 3.2 Extended scope (attempt only after core is complete — "should/could")

| Extension | Condition to start |
|---|---|
| LSTM forecaster | Core XGBoost pipeline evaluated (end of week 6) |
| Ablation A5 with a spatiotemporal GNN | LSTM done and ≥ 1 week remaining; see [11 §7](11_SPATIAL_INTELLIGENCE.md) |
| Density-map counter (CSRNet/DM-Count pre-trained weights) for dense zones | Detector MAE in the dense band is unacceptable on our footage |
| Live RTSP camera ingestion | Recorded-video pipeline stable |
| Camera homography for metric speed $v_i$ | Floor reference points measurable at recording site |
| Route recommendations | All of the above; treated as future work by default |

### 3.3 Explicitly out of scope

- Facial recognition, identity tracking, cross-camera re-identification, demographic inference.
- Guest-facing mobile app; automated control of gates/signage.
- Cloud-scale multi-tenant deployment; Kubernetes; microservices.
- Safety certification.

## 4. Assumptions

| ID | Assumption | Consequence if false |
|---|---|---|
| AS1 | Cameras are fixed and elevated; each zone has at least partial coverage | Zone occupancy must be extrapolated (coverage factor) or the zone is marked unobserved |
| AS2 | The event schedule is published before the event and changes are entered by the organiser | Schedule features become noisy; ablation A3 may show no gain |
| AS3 | One aggregation interval Δt = 1 min is sufficient for 5–30-min forecasting | A finer interval adds noise; a coarser one loses 5-min resolution |
| AS4 | The team has at least one machine with an NVIDIA GPU (≥ 6 GB) or accepts slower CPU processing | CV runs below real time; demo uses pre-processed observations |
| AS5 | Ethical permission can be obtained to record a campus event or a staged scenario | Real data limited to public datasets and synthetic data |
| AS6 | Planning capacity $C_i$ per zone is supplied by the organiser | Default $C_i = A_i \times \rho_{plan}$ with a documented default $\rho_{plan}$ |

## 5. Constraints

- Team of 3–4 students; 6–8 weeks to a working prototype.
- Free/open-source tools only; no paid cloud services required.
- Must demonstrate on recorded or simulated footage.
- Architecture: modular monolith ([07](07_SYSTEM_ARCHITECTURE.md)).

## 6. Deliverables

1. Source code (backend, CV worker, simulator, ML pipeline, frontend) — *later phase*.
2. This documentation package.
3. A recorded demo using replayed footage and/or synthetic streams.
4. An evaluation report with real numbers produced by the pipeline (no results are claimed here; they are generated into [16 §9](16_MODEL_EVALUATION.md) from logged runs).

## 7. Solo scope (v0.2, WORKFLOW 0.3.1)

The project is built by **one developer on one CPU-only laptop** with no hard deadline (decisions D1–D8 in `WORKFLOW.md`). This section records how the objectives, scope, assumptions and constraints above changed. Results are not stated here; they are in `EXPERIMENT_LOG.md` and [16](16_MODEL_EVALUATION.md).

### 7.1 Objectives

| ID | Change |
|---|---|
| O1, O2 | Measured on **public datasets** (Mall, ShanghaiTech Part B, MOT20), not on own annotated footage (D6: no own recordings). Density bands by true count where no calibrated areas exist |
| O3 | Unchanged. A minute without frames produces no row rather than a MISSING row ([08](08_MODULE_DESIGN.md) M3) |
| O4–O6 | Unchanged, but evaluated on **SYNTHETIC** events (CROWDSIM, clean and noisy): there is no REAL forecasting dataset, so forecasting conclusions are synthetic evidence |
| O7 | The 5-person usability walkthrough is **out of scope**; at most an informal walkthrough, reported as such |
| O8 | Ablations A1–A4 plus A4 without neighbour features (A4_NONBR). A5 (GNN) is an extension, not core |

### 7.2 Scope

| Area | Change from §3 |
|---|---|
| Configuration | Venues, events, schedules and cameras come from **YAML files** ([12 §6](12_DATASET_AND_DATA_COLLECTION.md)); no configuration UI, no polygon editor. Camera DB tables exist but are unused ([13 §3.10](13_DATABASE_DESIGN.md)) |
| Vision | YOLOX (Apache-2.0, D2) via ONNX Runtime on the **CPU, offline**, with tiling; in-house ByteTrack. No Ultralytics/YOLO11 |
| Data | CSV/annotation import is **not built** (D6; WORKFLOW Deviation log) |
| Forecasting | Baselines B0–B3 and XGBoost quantile models with split-conformal intervals. **LSTM moved to extended scope** |
| API | **No authentication or roles** (D7) — out of scope for the prototype, listed as a limitation |
| Dashboard | Five pages (Live, Predictions, Alerts, History, Event & venue), no login ([15 §7](15_FRONTEND_SPECIFICATION.md)) |
| Extended (§3.2) | LSTM, GNN (A5), density-map counter, RTSP and homography remain extensions with the start conditions in `WORKFLOW.md`; none has been started |
| Out of scope (§3.3) | Adds: authentication and role-based access, own video recordings, the formal usability study |

### 7.3 Assumptions and constraints

| Item | Status |
|---|---|
| AS4 (GPU available) | **False.** No NVIDIA GPU; CV runs offline on the CPU and the demo replays stored observations |
| AS5 (permission to record) | **Not pursued** (D6). Real data is limited to public datasets, used for CV evaluation only |
| AS1–AS3, AS6 | Unchanged; AS1 and AS6 are satisfied by construction in the synthetic venues |
| Constraints (§5) | One developer, no hard deadline (D5); free/open-source tools only; recorded or simulated footage only; modular monolith |
| Deliverables (§6) | Unchanged; the "CV worker" is the CLI `tools.vision.run_camera` |

## 8. Change log

| Version | Date | Change |
|---|---|---|
| 0.2 | 2026-11-23 | §7 solo scope added (WORKFLOW 0.3.1, 9.4 audit) |
| 0.1 | — | Design baseline (team plan) |

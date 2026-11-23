# CROWDCAST Documentation Index

| Field | Value |
|---|---|
| Version | 0.2 |
| Date | 15 Nov 2026 (v0.1 design baseline); 23 Nov 2026 (v0.2) |
| Status | Design baseline, **now implemented in a solo, CPU-only scope** tracked in [`WORKFLOW.md`](../WORKFLOW.md). Documents amended in the 9.4 audit carry a "Solo implementation" section that wins over their design text ([AUDIT_9_4.md](AUDIT_9_4.md)). Results exist only in [`EXPERIMENT_LOG.md`](../EXPERIMENT_LOG.md); none are stated in this index |

---

## 1. Project summary

CROWDCAST is a decision-support prototype for event organisers. It estimates per-zone crowd occupancy and boundary flows from recorded or simulated event video, forecasts each zone's occupancy 5, 15 and 30 minutes ahead with prediction intervals, classifies predicted congestion levels against organiser-defined capacities, and alerts operators early. Its research component tests whether **event-schedule** and **neighbouring-zone** information improve forecasts and warning lead time over independent zone-wise models.

## 2. Documentation navigation

| Area | Document | Contents |
|---|---|---|
| Start | [README](../README.md), [PROJECT_OVERVIEW](../PROJECT_OVERVIEW.md) | Orientation |
| Problem | [01 Problem statement](01_PROBLEM_STATEMENT.md) | Motivation, problem taxonomy, formal statement, users |
| | [02 Objectives & scope](02_OBJECTIVES_AND_SCOPE.md) | Objectives O1–O8, core vs extended scope, assumptions |
| Research | [03 Literature review](03_LITERATURE_REVIEW.md) | Structured review with verification tags |
| | [04 Existing systems](04_EXISTING_SYSTEMS.md) | CrowdVision, WaitTime, Density, academic systems |
| | [05 Gap analysis](05_GAP_ANALYSIS.md) | Candidate gaps, central contribution, non-claims |
| Specification | [06 Requirements (SRS)](06_REQUIREMENTS_SPECIFICATION.md) | FR/NFR with IDs and acceptance criteria |
| Design | [07 System architecture](07_SYSTEM_ARCHITECTURE.md) | Modular monolith, components, flows, decisions AD-01…AD-11 |
| | [08 Module design](08_MODULE_DESIGN.md) | M1–M9 interfaces, risk score, alert state machine |
| | [09 CV methodology](09_COMPUTER_VISION_METHODOLOGY.md) | Detection, tracking, zone counting, flows, dense crowds |
| | [10 ML forecasting](10_ML_FORECASTING_METHODOLOGY.md) | Problem maths, conservation, models, features, leakage |
| | [11 Spatial intelligence](11_SPATIAL_INTELLIGENCE.md) | Venue graph, levels, propagation, GNN justification |
| | [12 Datasets & collection](12_DATASET_AND_DATA_COLLECTION.md) | Public datasets, real collection, CROWDSIM |
| | [13 Database](13_DATABASE_DESIGN.md) | PostgreSQL schema, indexes, examples |
| | [14 API](14_API_SPECIFICATION.md) | REST endpoints, JSON, errors |
| | [15 Frontend](15_FRONTEND_SPECIFICATION.md) | Design system, pages |
| Quality | [16 Model evaluation](16_MODEL_EVALUATION.md) | CV, forecast, classification, operational metrics |
| | [17 Testing](17_TESTING_STRATEGY.md) | Test levels and test cases |
| Operations | [18 Deployment](18_DEPLOYMENT_PLAN.md) | Docker Compose, hardware |
| | [19 Security & privacy](19_SECURITY_AND_PRIVACY.md) | Threats, RBAC, retention, ethics |
| | [20 Limitations & future work](20_LIMITATIONS_AND_FUTURE_WORK.md) | L1–L13, future directions |
| Plan | [21 Roadmap](21_DEVELOPMENT_ROADMAP.md) | 8-week plan and priorities |
| Diagrams | [system_architecture](../ARCHITECTURE/system_architecture.mmd), [data_flow](../ARCHITECTURE/data_flow.mmd), [ml_pipeline](../ARCHITECTURE/ml_pipeline.mmd), [deployment_architecture](../ARCHITECTURE/deployment_architecture.mmd), [database_er](../ARCHITECTURE/database_er.mmd) | Mermaid sources |
| Research | [research_questions](../RESEARCH/research_questions.md), [research_hypotheses](../RESEARCH/research_hypotheses.md), [experimental_design](../RESEARCH/experimental_design.md), [bibliography](../RESEARCH/bibliography.md) | Research component |
| Management | [milestones](../PROJECT_MANAGEMENT/milestones.md), [task_breakdown](../PROJECT_MANAGEMENT/task_breakdown.md), [risk_register](../PROJECT_MANAGEMENT/risk_register.md), [team_responsibilities](../PROJECT_MANAGEMENT/team_responsibilities.md) | Planning |

## 3. Notation

Used identically in all documents.

| Symbol / term | Meaning |
|---|---|
| $G=(V,E)$ | Venue graph; $V$ zones (+ virtual outside node $\omega$), $E$ directed pedestrian connections |
| $i, j$ | Zone indices |
| $t$ | 1-minute time bucket index; $\Delta t = 1$ min |
| $h \in \{5, 15, 30\}$ | Forecast horizon (minutes) |
| $N_i(t)$ | Estimated occupancy (persons) |
| $F^{in}_i(t), F^{out}_i(t)$ | Persons entering / leaving zone $i$ during bucket $t$ |
| $F_{j\to i}(t)$ | Persons crossing from $j$ to $i$ |
| $v_i(t)$ | Mean walking speed (m/s), optional |
| $X_i(t)$ | State vector $[N_i, v_i, F^{in}_i, F^{out}_i]$ |
| $A_i$, $C_i$ | Usable area (m²), planning capacity (persons) |
| $u_i(t) = N_i/C_i$ | Occupancy ratio |
| $\rho_i(t) = N_i/A_i$ | Density (persons/m²) |
| $\tilde N_i(t)$ | Conservation-fused occupancy estimate |
| $\hat N^{(q)}_i(t+h)$ | Forecast quantile $q \in \{0.1, 0.5, 0.9\}$ (P10/P50/P90) |
| Levels | NORMAL $u<0.60$; ELEVATED $0.60\le u<0.80$; HIGH $0.80 \le u < 0.95$; CRITICAL $u \ge 0.95$ (defaults, configurable) |
| Congestion episode | True $u \ge 0.80$ for ≥ 2 consecutive minutes |
| Data origin | `REAL`, `MANUAL`, `SYNTHETIC` |
| M1–M9, T1–T2 | Modules / tools ([07 §2](07_SYSTEM_ARCHITECTURE.md)) |
| A1–A5 | Ablation configurations ([experimental_design](../RESEARCH/experimental_design.md)) |
| B0–B3 | Baselines: persistence, moving average, linear trend, conservation extrapolation |
| MS0–MS6 | Milestones |
| V1, V2, V3 | Synthetic venue topologies (festival, concert/stadium, exhibition — V3 held out) |

## 4. Technical decisions (summary)

| ID | Decision | Main alternative(s) | Reason (short) |
|---|---|---|---|
| AD-01 | Modular monolith, 3 processes (api, scheduler, cv-worker) | Microservices, single process | Isolation of heavy CV and timed jobs without broker overhead |
| AD-02 | Single ingestion contract for CV, simulator and annotations | Separate paths | Synthetic demo identical to real; provenance explicit |
| AD-03 | Polling dashboard (SSE later) | WebSockets | Simpler, meets latency requirements |
| AD-04 | Python 3.11 + FastAPI | Django, Node | Same language as ML/CV; validation; OpenAPI |
| AD-05 | PostgreSQL 16 (plain tables) | TimescaleDB, InfluxDB | Brief requirement; small data volume |
| AD-06 / CV-01 | YOLO11 + ByteTrack; density map as optional fallback | Density-only, DeepSORT, YOLOX | Counts **and** flows; no training; motion-only tracking for privacy |
| AD-07 / ML-01 | XGBoost quantile (main), LSTM (advanced), GNN (stretch); persistence baseline | Deep models first | Data volume, interpretability, quick iteration |
| AD-08 | React + TypeScript dashboard | Streamlit | Multi-page operational UI |
| AD-09 | SVG floor-plan map | GIS map | Venue-scale plans |
| AD-10 | APScheduler process | Celery | No broker needed |
| AD-11 | Docker Compose on one machine | Cloud/Kubernetes | Free, reproducible |
| — | Capacity-ratio thresholds set by organiser | Hard-coded densities | Safe density depends on context and regulation |
| — | Event-grouped splits + held-out venue | Random splits | Prevent leakage; test generalisation |
| — | Synthetic data (CROWDSIM) as main forecasting dataset | Only real data | Real temporal zone-level data unavailable at scale |

## 5. Core contribution

An **event-aware, graph-feature forecasting pipeline for venue-zone congestion and an ablation study** quantifying how much event-schedule features and neighbouring-zone features improve 5/15/30-minute forecasts and early-warning lead time over independent zone-wise models, including under realistic perception error. This is an empirical contribution at venue scale; the underlying methods are established ([05](05_GAP_ANALYSIS.md)).

## 6. Implementation priorities

1. Schema, auth, venue/zone/event CRUD.
2. CROWDSIM v1 + ingestion endpoint.
3. Persistence prediction cycle + risk engine + alerts (end-to-end without ML).
4. Live monitoring page.
5. CV worker (detection, tracking, regions, lines, aggregation).
6. XGBoost A4 with quantiles; ablations A1–A4.
7. Prediction, history, alerts pages.
8. Extensions by gate (LSTM, GNN, density maps, RTSP).

## 7. Outstanding questions

### 7.1 Research questions (tested on SYNTHETIC data 2026-11-23; results in [16 §9](16_MODEL_EVALUATION.md); the REAL-data parts remain open, D6)
RQ1–RQ6 and RQ-OP in [research_questions.md](../RESEARCH/research_questions.md). In particular: does schedule information help on *real* data (RQ1, RQ5)? Is 30 minutes a usable horizon (RQ3)? Do neighbour features help at ≤ 15 zones (RQ4)?

### 7.2 Decisions required from the team (answered 2026-11-20, WORKFLOW decision log D1–D8)
1. **Team size and roles:** 3 or 4 members? Who takes which role?
2. **Recording:** which real setting — staged volunteer scenario, a campus event, or both? Who submits the ethics application?
3. **Hardware:** which machine has an NVIDIA GPU for CV and the demo?
4. **Licence:** is AGPL-3.0 (Ultralytics) acceptable for the repository, or should the project use YOLOX (Apache-2.0)?
5. **Repository visibility:** public or private? (Affects dataset redistribution and footage rules.)
6. **Venue for the demo:** which real or fictional venue layout and capacities? Who acts as "organiser" to supply capacities?
7. **Course deadlines:** exact start date and whether weeks 9–10 are available for extensions.
8. **Language/framework comfort:** is the frontend team comfortable with React + TypeScript, or should scope shift to a simpler UI?

**Answers** (solo project; full text in the WORKFLOW decision log):

| Question | Answer |
|---|---|
| 1. Team size and roles | One developer holds every role ([team_responsibilities.md](../PROJECT_MANAGEMENT/team_responsibilities.md)) |
| 2. Recording | No own recordings (D6): public datasets only (Mall, ShanghaiTech Part B, MOT20, plus a public clip for the CV demo); no ethics application needed |
| 3. Hardware | No NVIDIA GPU: CV runs offline on the CPU (Ryzen 7 8840HS); the demo replays stored observations |
| 4. Licence | YOLOX (Apache-2.0) via ONNX Runtime (D2); Ultralytics not used |
| 5. Repository visibility | Public GitHub repository (D3); no datasets, footage or weights committed |
| 6. Demo venue | Split demo (D4): forecasting and alerts on the synthetic V1 festival venue; CV on a public clip with an illustrative venue |
| 7. Deadlines | No hard deadline (D5); started 2026-11-20, about a 10-week self-paced target |
| 8. Frontend framework | React 18 + TypeScript + Vite (D1), reduced to five pages |
| (added) Authentication | None (D7), stated as a limitation |

## 8. Consistency audit (Phase 4)

Performed on this documentation set (v0.1).

| Check | Result | Notes / fixes applied |
|---|---|---|
| All modules fit the architecture | ✔ | M1–M9, T1–T2 appear identically in 07, 08, diagrams, task breakdown |
| APIs match the database | ✔ | Every API resource maps to tables ([14 §4](14_API_SPECIFICATION.md)); observation fields = `crowd_observations` columns; prediction fields = `predictions` columns |
| Example values consistent | ✔ | Risk scores in API/DB examples recomputed from the formula in [08 §M7](08_MODULE_DESIGN.md) (0.17 / 0.76 / 0.70); levels match thresholds |
| Double-counting rule enforced in schema | ✔ | `counting_lines.connection_id` UNIQUE and one primary camera per zone — CV doc aligned with DB |
| ML inputs match available data | ✔ with caveat | $v_i$ only for calibrated cameras → declared optional (NaN-tolerant); flows unavailable on unobserved edges → graph validation warns; schedule only as published |
| Evaluation metrics match objectives | ✔ | O1/O2 → CV metrics; O4 → MAE/skill; O5 → P/R/F1; O6 → lead time/FAR/misses; O8 → ablation statistics |
| Hypothesis numbering | ✔ | H1–H7 used consistently (H5 = GNN question) |
| Ablation definitions | ✔ | A1–A5 identical in 10 §5.5 and experimental design; extra control A4\NBR documented in experimental design |
| Timeline achievable | ⚠ tight | 108 pd core vs ≈ 128 pd capacity (4 people); ML role heaviest — CV lead takes ablation execution; 3-member variant reduces UI scope |
| Research claims have credible references | ✔ with action | All citations in [bibliography](../RESEARCH/bibliography.md) with V/K tags; K entries require pre-submission verification; no numerical paper results quoted |
| Existing-system claims evidence-based | ✔ | Only vendor-page statements; "not advertised" ≠ "absent"; DensityAI excluded as unverifiable |
| Proposed vs implemented | ✔ | Every document marked Proposed; no results claimed |
| Synthetic vs real labelling | ✔ | `data_origin` in DB/API/UI; separate result tables |

Known residual inconsistencies to watch during implementation: interface signatures in [08](08_MODULE_DESIGN.md) are design-level and may be refined; any change must update [13](13_DATABASE_DESIGN.md)/[14](14_API_SPECIFICATION.md) in the same PR.

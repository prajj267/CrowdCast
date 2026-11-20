# 05 — Gap Analysis

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed; claims of novelty deliberately limited |

---

## 1. Method

Each candidate direction from the project brief is assessed against the literature ([03](03_LITERATURE_REVIEW.md)) and existing systems ([04](04_EXISTING_SYSTEMS.md)) on three questions:

1. **Already addressed?** — Is there published work doing essentially this?
2. **Feasible for us?** — Data, time (8 weeks), team skills.
3. **Testable?** — Can we produce a falsifiable result with our data?

## 2. Assessment of candidate directions

| # | Direction | Already addressed in research? | Our assessment | Feasible | Testable |
|---|---|---|---|---|---|
| D1 | Combine visual crowd estimation with **event schedules** | External factors (weather, holidays) are used in citywide flow forecasting [19]; big-event forecasting exists [24] but uses recent dynamics rather than an explicit programme. Schedule-driven forecasting of venue zones from camera counts was **not found** in our (limited) search | Plausible gap at *venue scale*; we cannot claim it is unaddressed everywhere — our search was not exhaustive | High — schedule is easy to encode | Yes — ablation A1 vs A3 |
| D2 | Predict congestion across **interconnected zones** | Extensively addressed for road traffic and city grids [20]–[23] | Not novel as a method. Novelty, if any, is only in the setting (small venue graph) | High | Yes |
| D3 | Model **propagation** of congestion between zones | Graph diffusion models [20] and traffic-wave theory [48] address propagation | Not novel as a method; useful engineering via lagged neighbour features | Medium | Yes — A4 vs A2 |
| D4 | Incorporate **inflow/outflow** | Core state in [19]; flows used in [24] | Not novel; necessary baseline ingredient | Medium — depends on tracking quality | Yes — A2 vs A1 |
| D5 | Predictions with **uncertainty** | Addressed for traffic GNNs [38]; general methods [36], [37] | Not novel as method; valuable operationally | High (quantile boosting + conformal) | Yes — coverage |

## 3. What is genuinely open for this project

Our honest reading:

- None of D1–D5 is a new *method*.
- What we did not find in the literature is a **controlled, reproducible study at event-venue scale** that measures, with camera-derived zone counts, **how much** (if at all) an explicit event schedule and neighbouring-zone states improve 5/15/30-minute congestion forecasts and **warning lead time** compared with independent zone-wise models — including how perception errors propagate into those gains.
- This is an **empirical** contribution, appropriate for a student project, and can produce a useful result whether the hypotheses are confirmed or refuted.

## 4. Recommended central technical contribution

> **An event-aware, graph-feature forecasting pipeline for venue-zone congestion, and an ablation study that quantifies the contribution of event-schedule features and neighbouring-zone features to multi-horizon forecast accuracy and early-warning lead time, using gradient-boosted quantile models evaluated on held-out events.**

Concretely:

1. A zone-level state representation $X_i(t)$ produced from video (counts + line-crossing flows), fused with an occupancy-conservation estimate.
2. Feature groups: history, flow, schedule, neighbour (graph-derived) — §5 of [10](10_ML_FORECASTING_METHODOLOGY.md).
3. Ablation A1–A4 (core) and A5 (GNN, stretch) — [experimental_design.md](../RESEARCH/experimental_design.md).
4. Evaluation by both error metrics and operational metrics (lead time, false alarms).

**Why this and not a new GNN architecture:** a new architecture would require data volume and time the team does not have, and novelty claims would be hard to defend. The ablation design produces a defensible answer with modest models, and the GNN remains an optional extension.

## 5. Explicit non-claims

- We do not claim to be the first to forecast crowds at events [24], [26].
- We do not claim better counting accuracy than published methods or commercial products.
- We do not claim any results until experiments are run; all improvements are **hypotheses** (H1–H7, [research_hypotheses.md](../RESEARCH/research_hypotheses.md)).
- Synthetic-data findings will be reported as synthetic and not generalised to real venues without real-data evidence.

## 6. Residual risk to the contribution

| Risk | Effect | Mitigation |
|---|---|---|
| Synthetic data encodes the hypothesis (the simulator uses the schedule, so schedule features trivially help) | Inflated A3 gain | Simulator parameters randomised; schedule *perturbed* relative to true dynamics (delays, no-shows); report real-data check separately |
| Too little real data to confirm | Conclusions limited to synthetic | State this limitation; prioritise at least one real recorded session |
| CV flow errors swamp feature gains | A2/A4 gains vanish on real data | Report results on ground-truth flows *and* CV-estimated flows (perception-error study, RQ5) |

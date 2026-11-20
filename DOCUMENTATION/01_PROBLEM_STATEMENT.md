# 01 — Problem Statement

| Field | Value |
|---|---|
| Document | 01_PROBLEM_STATEMENT |
| Version | 0.1 (design baseline) |
| Status | Proposed — nothing described here is implemented yet |
| Notation | See [INDEX.md §3 Notation](INDEX.md#3-notation) |

---

## 1. Context

Large public events — college festivals, concerts, cultural festivals, exhibitions, stadium fixtures — concentrate thousands of people into a bounded venue for a few hours. Pedestrian demand inside such venues is **strongly non-stationary**: it is driven by the event programme (a headline act starting, a meal break, the final exit wave), not by a smooth daily cycle. Demand also **moves**: when a performance ends, the occupancy of the stage area falls while connecting corridors, food courts and exits fill in a predictable sequence.

## 2. Why crowd congestion matters

1. **Safety.** Empirical analysis of crowd disasters shows that dangerous conditions develop when local density becomes very high and the crowd transitions from smooth flow to stop-and-go waves and then to "crowd turbulence" [30]. These transitions are a function of local density and flow, not of total attendance alone, which is why *zone-level* monitoring matters.
2. **Operations.** Congestion at food courts, toilets, entry gates and stalls produces long queues, missed performances and overloaded staff, even when there is no safety risk.
3. **Planning.** Pedestrian level-of-service concepts [31], [32] relate available space per person to comfort and throughput. Organisers plan staffing and barriers around such capacities, but typically compare only *current* conditions to them.

## 3. Why reactive monitoring is insufficient

Conventional CCTV-based monitoring — by human operators or automated counting — answers *"where is it crowded now?"*. This has three weaknesses:

- **Response latency.** Opening a gate, redirecting stewards or pausing an entry stream takes minutes. If congestion is detected only once it exists, the intervention arrives late.
- **Propagation.** Congestion in one zone is often the downstream consequence of a release elsewhere (a stage emptying into a corridor). Watching zones independently misses the causal chain that would allow earlier warning.
- **Operator load.** A small operations team cannot watch many feeds continuously; reactive monitoring depends on someone looking at the right feed at the right time.

## 4. Why forecasting is useful

A forecast of zone occupancy 5, 15 and 30 minutes ahead converts monitoring into **anticipation**:

| Horizon | Typical operational use (assumption — to be validated with organisers) |
|---|---|
| 5 min | Tactical: dispatch nearby stewards, open a side lane, briefly hold an entry stream |
| 15 min | Short-term: reposition staff, make PA announcements, stagger releases |
| 30 min | Pre-emptive: adjust programme timing, open overflow areas, brief security leads |

These horizons are **targets**. Whether useful accuracy is achievable at each horizon is an open research question ([research_questions.md](../RESEARCH/research_questions.md), RQ3), not an established result.

## 5. Distinguishing the four related problems

The literature uses these terms loosely. CROWDCAST uses them as follows:

| Problem | Question answered | Typical input | Typical output | Example methods |
|---|---|---|---|---|
| **Crowd counting** | How many people are in this image/region now? | One frame | Scalar count $\hat N$ | Detect-and-count; integral of a density map [1], [2] |
| **Crowd density estimation** | How are people distributed over space now? | One frame | Density map $D(x,y)$ with $\sum D \approx N$, or persons/m² per zone | Density-map CNNs [1], [2], [6] |
| **Crowd flow estimation** | How many people cross a boundary, in which direction, how fast? | Video (temporal) | Inflow/outflow rates $F^{in}, F^{out}$ (persons/min), speed $v$ | Multi-object tracking + line crossing [14], [16] |
| **Congestion prediction** | Which zones will exceed a critical level in the next $h$ minutes? | Time series of the above + schedule + venue graph | $\hat N_i(t+h)$, risk level, alerts | Time-series / spatiotemporal forecasting [19]–[24] |

The first three are **perception** problems (estimating the present). The fourth is a **forecasting** problem that consumes their outputs. Perception errors propagate into forecasts, so CROWDCAST evaluates both stages separately and jointly ([16_MODEL_EVALUATION.md](16_MODEL_EVALUATION.md)).

## 6. Formal problem statement

Given:

- a venue represented as a graph $G=(V,E)$ of zones ([11_SPATIAL_INTELLIGENCE.md](11_SPATIAL_INTELLIGENCE.md));
- for each zone $i$ and each aggregation interval $t$ ($\Delta t = 1$ min) an estimated state $X_i(t) = [N_i(t), v_i(t), F^{in}_i(t), F^{out}_i(t)]$ derived from video;
- the published event schedule $S$;

predict $\hat N_i(t+h)$ with a prediction interval for $h \in \{5, 15, 30\}$ minutes, classify each zone's predicted congestion level $\hat L_i(t+h)$, and raise alerts early enough to permit intervention while keeping false alarms low enough that operators trust the system.

## 7. Technical challenges

| # | Challenge | Why it is hard | Addressed in |
|---|---|---|---|
| C1 | Counting accuracy degrades with density | Occlusion makes person detectors miss people; density-map methods do better but give no tracks | [09](09_COMPUTER_VISION_METHODOLOGY.md) |
| C2 | Flow estimation needs reliable tracking | ID switches and fragmented tracks cause double or missed crossings | [09](09_COMPUTER_VISION_METHODOLOGY.md) §6 |
| C3 | Partial camera coverage | Blind spots break flow conservation | [09](09_COMPUTER_VISION_METHODOLOGY.md), [20](20_LIMITATIONS_AND_FUTURE_WORK.md) |
| C4 | Non-stationary, schedule-driven demand | Historical averages fail when programme timing changes | [10](10_ML_FORECASTING_METHODOLOGY.md) §5 |
| C5 | Scarce labelled temporal data | Public datasets are image-level, not event-zone time series | [12](12_DATASET_AND_DATA_COLLECTION.md) |
| C6 | Spatial coupling | Occupancy depends on neighbours with a travel-time lag | [11](11_SPATIAL_INTELLIGENCE.md) |
| C7 | Rare positive class | Congestion is rare; accuracy hides poor recall | [16](16_MODEL_EVALUATION.md) |
| C8 | Privacy | Cameras capture identifiable people | [19](19_SECURITY_AND_PRIVACY.md) |

## 8. Intended users

| Role | Description | Primary needs |
|---|---|---|
| **Administrator** | Technical owner of a deployment | User accounts, camera registration, model activation, data retention |
| **Event organiser** | Plans the event | Venue/zone configuration, schedule entry, capacity thresholds, post-event analytics |
| **Monitoring operator** | Watches the dashboard during the event | Live map, forecasts, alerts, acknowledgement workflow |

Users are **operational staff**, not the public. No guest-facing app is in the initial scope.

## 9. Out of scope (initial prototype)

- Identification of individuals, facial recognition, or cross-camera re-identification.
- Automated control actions — CROWDCAST advises; humans decide.
- Certification as a safety system. CROWDCAST is a decision-support research prototype and must not be the sole basis for safety-critical decisions.

---
References: bracketed numbers refer to [RESEARCH/bibliography.md](../RESEARCH/bibliography.md).

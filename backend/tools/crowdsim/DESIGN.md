# CROWDSIM v1 — design note (WORKFLOW 3.2.1)

CROWDSIM generates the **SYNTHETIC** events used to train and evaluate the forecasting models
(doc 12 §5). It is not a validated pedestrian simulator: it is a transparent, seeded
agent model whose job is to produce zone-level time series with the mechanisms the research
question needs — schedule-driven surges, propagation between neighbouring zones with travel
lags, capacity bottlenecks with spillback, and an exit wave.

**Labels used below.** **[DOC]** = value or rule fixed in the documentation (cited).
**[PH]** = *placeholder* chosen for this note: plausible order of magnitude, **not calibrated
and not taken from a verified source**. Every [PH] value lives in one config file
(`configs/crowdsim/regime_a.yaml`) and must be called a placeholder wherever results are
reported. A second regime (§9) re-runs key results with different placeholders (doc 12 §5.5).

## 1. Time

| Item | Value | Label |
|---|---|---|
| Tick δ | 10 s | [DOC] 12 §5.1 |
| Output bucket | 1 min = 6 ticks; event time from the event's `start_time` (UTC) | [DOC] CLAUDE.md §4 |
| Simulated span | from `start_time` until the venue is empty or `end_time + 30 min` | [PH] |

**Bucket convention (needed for exact conservation).** For zone *i* and bucket *t*:
`N_i(t)` = occupancy at the **start** of the bucket; `F_in_i(t)`, `F_out_i(t)`, `F_{j→i}(t)` =
crossings **during** [t, t + 1 min). Hence `N_i(t+1) = N_i(t) + F_in_i(t) − F_out_i(t)` exactly,
and summed over zones the venue-level identity of doc 11 §5.1 holds exactly (test 3.4.1).

## 2. Agents and where they are counted

An agent has: current zone, destination, remaining route, a *busy* timer and a *dwell* timer.

- An agent is always counted in exactly one zone (never "on an edge"), so occupancy is well defined.
- Crossing edge (j → i) happens in one tick, when the edge has capacity left (§5). The agent is
  then in zone *i* and **busy for the edge's travel time τ_ji** (walking), scaled by congestion
  (§6), before it can cross again or start dwelling. This is how travel time produces the
  propagation lag the forecasting features rely on (doc 11 §5.2).
- Agents enter from OUTSIDE through entry edges and leave through exit edges. OUTSIDE is never on
  a route between two zones (same rule as `VenueGraph`).

## 3. Arrivals [DOC 12 §5.1 step 1]

Non-homogeneous Poisson process. Per tick, arrivals ~ Poisson(λ(t)·δ), split over entry edges in
proportion to their width [PH].

λ(t) = A_total · g(t), where g is a density over the event (integrates to 1):

- **Baseline** (weight 0.6 [PH]): ramps up linearly over the first 60 min [PH], flat, then falls
  linearly to 0 at `end_time − 60 min` [PH].
- **Pre-item surges** (weight 0.4 [PH] shared across items by `expected_attendance ×
  attraction_weight`): a Gaussian bump centred 20 min [PH] before each item's **published**
  start, σ = 15 min [PH].

A_total = `expected_attendance` × turnout factor ~ U(0.85, 1.05) [PH] per event.

## 4. Destination choice [DOC 12 §5.1 step 3]

When an agent's dwell ends it picks a destination *k* by multinomial logit:

`P(k | i, t) ∝ exp(β_a·a_k(t) − β_d·d_ik − β_c·u_k(t))`

- d_ik = shortest-path travel time in **minutes** from `VenueGraph.travel_time_matrix()`.
- u_k(t) = N_k / C_k (occupancy ratio, doc 11 §4).
- a_k(t) = base attraction of the zone type + Σ over **actual** (perturbed) items in *k* of
  `attraction_weight × popularity × h(t)`, where h = linear rise from 0 to 1 over the 30 min
  [PH] before the actual start, 1 during the item, 0 after.
- Choice set: all zones except entry/exit-only gates, plus **leave** (§7).

| Parameter | Value | Label |
|---|---|---|
| β_a (attraction) | 3.0 | [PH] |
| β_d (per minute of travel) | 0.15 | [PH] |
| β_c (crowding) | 2.0 | [PH] |
| Base attraction by zone type | STAGE 0.3, FOOD 0.4, EXHIBITION 0.3, OPEN_AREA 0.2, SEATING 0.2, FACILITY 0.15, CORRIDOR 0.0, OTHER 0.1 | [PH] |

## 5. Movement, capacity, queues and spillback [DOC 12 §5.1 step 4]

- Agents follow the fastest route (Dijkstra on τ) to their destination, one edge at a time.
- Edge throughput per tick ≤ q_max·δ with q_max = w_ji · q_s (doc 11 §3); q_s = 75 persons/m/min
  [PH; order of magnitude for walkways, **not verified at source**]. Fractional capacity carries
  over between ticks.
- Agents waiting for an edge form a FIFO queue **in zone j** (they still count in *j*).
- **Spillback:** an edge into zone *i* admits nobody while N_i ≥ jam capacity = 1.5 · C_i [PH];
  queues then grow upstream — the congestion propagation the models must anticipate.

## 6. Speed–density [DOC 12 §5.1 step 5]

v_i = v_free · max(0.1, 1 − ρ_i / ρ_jam), ρ_i = N_i / A_i.
Busy time after crossing into *i* = τ_ji · v_free / v_i (walking slows in a dense zone).
v_free = 1.3 m/s [PH], ρ_jam = 5.0 persons/m² [PH]. Output `mean_speed_mps` = bucket mean of v_i.

## 7. Dwell and departures [DOC 12 §5.1 steps 2, 6]

- **Dwell** on arrival at the destination: if a **PERFORMANCE, ANNOUNCEMENT or pop-up** item is
  running there (or starts within 30 min), until the item ends plus LogNormal(median 3 min,
  σ 0.5) [PH]. MEAL and OTHER items (e.g. lunch, an all-day exhibition) only raise attraction;
  visitors then stay the zone-type dwell. *(Revised 2026-11-20 after the 3.4.2 eye check: with
  "stay until any item ends", every exhibition visitor stayed 5 h and the food court sat at its jam
  limit for the whole lunch window.)* Otherwise LogNormal with median by zone type —
  FOOD 20, EXHIBITION 15, STAGE 10, OPEN_AREA 10, SEATING 15, FACILITY 5, CORRIDOR 1, OTHER 5 min,
  σ = 0.6 [PH].
- **Leave option** in the logit with utility `β_L · ℓ(t)`; ℓ rises linearly from 0 at the
  start to 1 at `end_time` and is +1 extra for 30 min after the final actual item ends (exit wave)
  [PH]; β_L = 2.5 [PH]. Leaving = route to the nearest exit edge, then OUTSIDE.
- At `end_time` every remaining agent's destination becomes *leave* (forced exit) [PH].

## 8. Schedule perturbation [DOC 12 §5.1 step 7]

The **published** schedule (from the event file) is what forecasting may use as features; the
**actual** schedule drives the agents and is written out for analysis only (doc 10 §7).

| Perturbation | Value | Label |
|---|---|---|
| Actual start = published start + δ_s | δ_s ~ U(−5, +10) min, duration kept | [DOC] |
| Popularity multiplier per item | LogNormal(0, 0.3) | [DOC] |
| Pop-up attraction | **5 % chance per event-hour** [interpretation: the doc says "5 % chance", unit unstated], in a random non-gate zone, 20–45 min, attraction 0.6, not in the published schedule | [DOC] rate / [PH] rest |

## 9. Event generation and regimes

A venue + a schedule template make one event; CROWDSIM can also *generate* randomised events
(doc 12 §5.4: 60 per venue, 4–8 h). Generator ranges (all [PH]): duration U{4..8} h; 4–10
items; categories PERFORMANCE / MEAL / ANNOUNCEMENT / OTHER with zone by category (PERFORMANCE→
STAGE, MEAL→FOOD, OTHER→EXHIBITION/OPEN_AREA, ANNOUNCEMENT→STAGE); item length 20–90 min;
`expected_attendance` = U(0.6, 1.6) × Σ C_i; `attraction_weight` U(0.3, 1.0) rounded to 0.05;
ENTRY_OPEN at the start and EXIT_WAVE in the last 30 min, venue-wide.

**Regime A** = all values above. **Regime B** (sensitivity, doc 12 §5.5) changes: β_c 2.0 → 1.0,
q_s 75 → 50, base turnout U(0.85, 1.05) → U(0.7, 1.2), dwell medians × 1.5.

## 10. Observation noise (doc 12 §5.3) — implemented with replay, not in the core

`N_obs = round(N·(1 − m(ρ)) + ε)`, m(ρ) = min(0.6, m0 + m1·ρ), ε ~ N(0, (σ_r·N)²); each true
crossing detected with probability p_det; false crossings at rate r_fp per connection per
minute. **Placeholders until calibrated in 7.2.2:** m0 = 0.05, m1 = 0.08 per (person/m²),
σ_r = 0.05, p_det = 0.90, r_fp = 0.2 [all PH]. Clean output → `method = SIM_CLEAN`; noisy →
`SIM_NOISY`. Targets are always the clean N (doc 12 §5.3).

## 11. Seeds and reproducibility

- One `numpy.random.Generator` (PCG64) per event, from `SeedSequence(master_seed).spawn(...)`;
  master seed **2027** (same as `splits.json`, CLAUDE.md §5). Same inputs + seed → identical
  output (unit test).
- Each output file records: CROWDSIM version, git commit, regime name, master seed, event index,
  venue file hash, and `data_origin = SYNTHETIC`.

## 12. Outputs (doc 12 §5.2, §6) — Parquet, one directory per event

| File | Columns |
|---|---|
| `zone_minutes.parquet` | event_id, zone_code, bucket_start, occupancy (N), inflow, outflow, mean_speed_mps, data_origin = SYNTHETIC |
| `edge_flows.parquet` | bucket_start, from_code, to_code (OUTSIDE allowed), flow |
| `schedule_published.parquet` / `schedule_actual.parquet` | title, category, zone_code, start, end, expected_attendance, attraction_weight (+ popularity, is_popup in actual) |
| `manifest.json` | §11 metadata |

## 13. Known simplifications (state them in the report)

Agents are homogeneous (no groups, no ages, no mobility differences); no within-zone geometry;
routes ignore congestion (fixed fastest path); capacity is per edge, not per door width over
time; all behavioural parameters are placeholders. Forecasting results on CROWDSIM data are
**synthetic evidence** of whether the features *can* help under these mechanisms, not evidence
about real crowds (CLAUDE.md §7).

# 10 — ML Forecasting Methodology

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Proposed; **no forecasting results exist yet** |
| Module | M6, T2 |

---

## 1. Problem definition

### 1.1 Time base and state

Time is discretised into 1-minute buckets $t \in \{0, 1, \dots, T\}$ measured from event start ($\Delta t = 1$ min). For each zone $i \in V$:

$$
X_i(t) = \big[N_i(t),\; v_i(t),\; F^{in}_i(t),\; F^{out}_i(t)\big]
$$

| Symbol | Meaning | Unit | Source | May be missing? |
|---|---|---|---|---|
| $N_i(t)$ | Estimated occupancy at the end of bucket $t$ | persons | CV median count / simulator | Rarely (flagged) |
| $v_i(t)$ | Mean pedestrian speed | m/s | Calibrated cameras / simulator | **Often** (uncalibrated cameras) |
| $F^{in}_i(t)$ | Persons entering during bucket $t$ | persons/min | Line crossings | When boundaries unobserved |
| $F^{out}_i(t)$ | Persons leaving during bucket $t$ | persons/min | Line crossings | Same |

Additional known quantities: area $A_i$, capacity $C_i$, occupancy ratio $u_i(t) = N_i(t)/C_i$, the venue graph $G$, and the schedule $S$.

### 1.2 Forecasting task

At issue time $t$, using only information available at $t$, predict for each zone $i$ and horizon $h \in \mathcal{H} = \{5, 15, 30\}$:

$$
\hat N_i(t+h) = f_h\big(\{X_j(t-l)\}_{j \in V,\, 0 \le l < W},\; S,\; G,\; \text{static}_i\big)
$$

with look-back window $W = 30$ min (tunable), plus quantiles $\hat N^{(q)}_i(t+h)$ for $q \in \{0.1, 0.5, 0.9\}$.

The point forecast reported as "prediction" is the median $\hat N^{(0.5)}$.

### 1.3 Multi-horizon strategy

**Direct strategy:** one model per horizon (and quantile). Alternatives: recursive (one-step model iterated $h$ times — errors compound and requires forecasting exogenous inputs) and multi-output (one model, three outputs — natural for LSTM). Direct is chosen for tree models; the LSTM uses multi-output.

## 2. Baselines (must be implemented first)

| ID | Baseline | Formula | Why |
|---|---|---|---|
| B0 | Persistence | $\hat N_i(t+h) = N_i(t)$ | The minimum bar; surprisingly strong at 5 min |
| B1 | Moving average | $\hat N_i(t+h) = \frac1k\sum_{l=0}^{k-1} N_i(t-l)$, $k=5$ | Smooths noise; lags trends |
| B2 | Linear trend | $\hat N_i(t+h) = N_i(t) + h\cdot \hat\beta_i(t)$, $\hat\beta$ = OLS slope over last 10 min | Captures ramps |
| B3 | Conservation extrapolation | §3.2 | Physically motivated; uses flows |

Every learned model must be compared to **all** baselines at **each** horizon. A model that does not beat B0 at a horizon is reported as such.

## 3. Occupancy conservation

### 3.1 The conservation identity

If all boundaries of zone $i$ are observed and nobody appears or disappears inside the zone:

$$
N_i(t+\Delta t) = N_i(t) + F^{in}_i(t)\,\Delta t - F^{out}_i(t)\,\Delta t
$$

Summed over $h$ steps:

$$
N_i(t+h) = N_i(t) + \sum_{s=t}^{t+h-1}\big(F^{in}_i(s) - F^{out}_i(s)\big)\Delta t
$$

### 3.2 Baseline B3

Future flows are unknown, so B3 holds the recent mean net flow constant:

$$
\hat N_i(t+h) = \operatorname{clip}\Big(N_i(t) + h\cdot \bar q_i(t),\; 0,\; N^{max}_i\Big),\qquad
\bar q_i(t) = \frac1k\sum_{l=0}^{k-1}\big(F^{in}_i(t-l) - F^{out}_i(t-l)\big)
$$

with $k = 5$ and $N^{max}_i = 1.5\,C_i$ as a physical sanity cap.

### 3.3 Assumptions and limitations

| Assumption | When it fails | Consequence |
|---|---|---|
| All boundaries are observed by counting lines | Unmonitored doors, open-sided outdoor zones | Missing flow terms → biased net flow |
| No sources/sinks inside the zone | People emerging from tents/toilets inside the zone | Same |
| Flows are measured without error | Missed/duplicated crossings | **Errors accumulate**: if each minute's net-flow error is independent with variance $\sigma^2$, integrated occupancy error variance grows as $h\sigma^2$ — a random walk. Even a small systematic bias $b$ produces drift $h\cdot b$ |
| Flows stay constant over $h$ | Schedule-driven surges (stage release) | Large errors at 15–30 min — exactly where forecasting matters |
| $N_i(t)$ known exactly | Detector undercount | Offsets every forecast |

Hence conservation is used in two ways: (a) as baseline B3; (b) as a **state-estimation filter** combining two independent noisy estimates of current occupancy (§3.4). It is not, by itself, a forecasting model for longer horizons.

### 3.4 Conservation fusion (state estimation)

A complementary filter (a steady-state Kalman filter with scalar gain):

$$
\tilde N_i(t) = \alpha_i\, N^{cv}_i(t) + (1-\alpha_i)\big(\tilde N_i(t-1) + F^{in}_i(t) - F^{out}_i(t)\big)
$$

- $\alpha_i \in [0,1]$ trades trust in direct counting vs flow integration. Default $\alpha=0.5$; lowered (e.g. 0.3) when the window is `LOW_CONFIDENCE` (direct counts unreliable), raised to 1 when flows are missing.
- The flow term re-anchors to the direct count every step, so flow-integration drift cannot grow unbounded.
- $\tilde N_i$ is offered as an **additional feature**, not a replacement of $N^{cv}_i$, so the learned model can choose. The ablation reports whether it helps.

## 4. Candidate models

| Model | Input form | Strengths | Weaknesses | Role |
|---|---|---|---|---|
| Random Forest [33] | Tabular features | Robust, few hyper-parameters, little overfitting | No native quantiles (quantile forests exist); cannot extrapolate; larger models | Comparison model |
| **XGBoost** [34] | Tabular features | Strong on lagged tabular data; handles missing values natively; quantile objective (`reg:quantileerror`, XGBoost ≥ 2.0); fast | Cannot extrapolate beyond target range; needs feature engineering | **Recommended main model** |
| LSTM [35] | Sequences $W \times d$ | Learns temporal patterns without hand-crafted lags; multi-output | Needs more data; sensitive to tuning; slower to iterate | **Recommended advanced comparison** |
| Spatiotemporal GNN (STGCN [21] / Graph WaveNet [22]) | Graph signal over time | Explicitly models spatial propagation | Data-hungry; ≤ 15 nodes gives little to learn; complex | **Stretch (A5)** |

### Decision ML-01

| Item | Content |
|---|---|
| Baseline model | **B0 persistence** (reference for skill scores) plus B1–B3 |
| Recommended main model | **Global XGBoost quantile regressor**, direct strategy, one booster per (horizon, quantile) = 9 boosters |
| Advanced model | **Global LSTM** with quantile (pinball) loss, multi-horizon output |
| Stretch | Small STGCN-style GNN for ablation A5 |
| Reason | Our data are hours per event, ≤ 15 zones, tens of events (mostly synthetic). Gradient boosting is the best-supported choice for small tabular time-series data with exogenous features; the LSTM tests whether learned temporal representations add value; a GNN is justified only if A4 shows neighbour information matters *and* XGBoost cannot exploit it through features |
| Trade-off | Feature engineering effort; graph structure only enters through hand-designed neighbour features |

"Global" means one model trained on all zones (zone type and capacity as features), which multiplies training data per model compared with one model per zone and enables prediction for new zones.

## 5. Feature engineering

All features at issue time $t$ use only data with bucket $\le t$ (§7). Feature groups map one-to-one onto ablation configurations.

### 5.1 F_HIST — historical occupancy (all configurations)

| Feature | Definition |
|---|---|
| `u_t` | $u_i(t)$ |
| `u_lag_l` | $u_i(t-l)$, $l \in \{1,2,3,5,10,15,30\}$ |
| `u_roll_mean_k`, `u_roll_std_k` | Rolling mean/std over $k \in \{5, 15\}$ |
| `u_slope_10` | OLS slope of $u_i$ over last 10 min |
| `n_t` | $N_i(t)$ (absolute scale) |
| `fused_u_t` | $\tilde N_i(t)/C_i$ (§3.4) |
| Static | `zone_type` (one-hot), `capacity`, `area`, `is_entry`, `is_exit`, `degree` |
| Time | `minutes_since_start`, `minutes_to_end`, `frac_elapsed` |

Wall-clock time-of-day is **not** used by default: events start at different times and synthetic events would leak artificial regularities. It can be enabled as a tested feature.

### 5.2 F_FLOW — inflow/outflow

| Feature | Definition |
|---|---|
| `fin_lag_l`, `fout_lag_l` | $F^{in}_i(t-l)$, $F^{out}_i(t-l)$ normalised by $C_i$, $l \in \{0,1,2,5\}$ |
| `net_sum_k` | $\sum_{l<k}(F^{in}-F^{out})/C_i$, $k \in \{5,15\}$ |
| `b3_pred_h` | Conservation-extrapolation forecast for the model's horizon |
| `speed_t`, `speed_roll_5` | $v_i$; **NaN if uncalibrated** (XGBoost handles NaN natively) |

### 5.3 F_SCHED — event schedule

Let $S_i$ be schedule items located in zone $i$ and $S_{\cdot}$ venue-wide items.

| Feature | Definition |
|---|---|
| `active_item_i` | 1 if an item is in progress in zone $i$ |
| `active_category_i` | One-hot of category (`PERFORMANCE`, `MEAL`, `ENTRY_OPEN`, `EXIT_WAVE`, `ANNOUNCEMENT`, `OTHER`) |
| `min_to_next_start_i` | Minutes until next item in zone $i$ starts (capped at 120) |
| `min_since_last_end_i` | Minutes since last item in zone $i$ ended (capped at 120) |
| `min_to_next_end_i` | Minutes until the active item ends (capped) |
| `next_item_attendance_i` | Organiser's expected attendance of next/active item ÷ $C_i$ |
| `attraction_i` | Organiser-supplied attraction weight of active/next item |
| `starts_within_h_i`, `ends_within_h_i` | Whether an item in zone $i$ starts/ends within the forecast horizon |
| `venue_items_ending_within_h` | Count of items anywhere ending within $h$ (release waves) |

Schedule features use only the **published** schedule (and its live edits), which is legitimately known at issue time. Realised attendance is never used.

### 5.4 F_NBR — neighbouring zones (graph-derived)

Using adjacency from [11](11_SPATIAL_INTELLIGENCE.md), with $\mathcal N^{in}(i)$ upstream neighbours and travel time $\tau_{ji}$ (minutes):

| Feature | Definition |
|---|---|
| `nbr_u_mean`, `nbr_u_max` | Mean/max $u_j(t)$ over $j \in \mathcal N(i)$ |
| `nbr_u_wmean` | Boundary-width-weighted mean $\sum_j w_{ji}u_j / \sum_j w_{ji}$ |
| `nbr_flow_to_i` | $\sum_{j} F_{j\to i}(t)$ measured on shared lines |
| `nbr_out_pressure` | $\sum_{j \in \mathcal N^{in}(i)} F^{out}_j(t)\cdot \pi_{j\to i}$ where $\pi_{j\to i}$ = historical share of $j$'s outflow going to $i$ (estimated from training data) |
| `nbr_u_slope` | Mean slope of $u_j$ over last 10 min |
| `nbr_sched_release_within_h` | Any upstream neighbour has an item ending within $h$ |
| `nbr_lagged_u_tau` | $u_j(t - \lfloor\tau_{ji}\rfloor)$ aggregated (captures propagation delay) |

### 5.5 Feature-set definitions (used in ablations)

| Config | Feature groups |
|---|---|
| A1 | F_HIST |
| A2 | F_HIST + F_FLOW |
| A3 | F_HIST + F_SCHED |
| A4 | F_HIST + F_FLOW + F_SCHED + F_NBR |
| A5 | A4 inputs + explicit graph model (GNN) |

## 6. Target formulation

Tree models cannot predict values outside the range of training targets and struggle with zones of different scale. Therefore the target is the **capacity-normalised change**:

$$
y_{i,h}(t) = \frac{N_i(t+h) - N_i(t)}{C_i}, \qquad \hat N_i(t+h) = \max\big(0,\; N_i(t) + C_i\,\hat y_{i,h}(t)\big)
$$

Quantile predictions are sorted after inverse transform to prevent quantile crossing (FR-FC-02).

**Ground truth for training:**
- Synthetic data: simulator true $N_i$ (clean target) — and separately, noisy "CV-like" $N_i$ as input.
- Real data: manual annotations where available; otherwise CV counts (documented as a noisy target).

## 7. Data leakage prevention

| Leak | Prevention |
|---|---|
| Future observations in rolling windows | All rolling features computed with `shift(0)` on data ≤ $t$ and windows closed on the right; unit test compares features computed on truncated vs full series (TC-ML-02) |
| Random row splits | **Splits are by event** (all minutes of an event in one split). Within an event, consecutive minutes are highly correlated; row-level splits would leak |
| Normalisation statistics | Scalers (LSTM) fitted on training events only |
| Schedule leakage | Only published schedule; no realised attendance; synthetic schedule perturbed (actual start may differ from published by ±10 min) |
| Outflow share $\pi_{j\to i}$ | Estimated on training events only |
| Targets beyond event end | Rows with $t+h > T$ dropped |
| Hyper-parameter tuning on test | Tuning uses grouped CV inside training events; test events evaluated **once** per final configuration |
| Missing-data imputation | Forward-fill only (never back-fill, which uses future values) |

## 8. Train–validation–test strategy

### 8.1 Synthetic data (primary experimental dataset)

| Split | Content |
|---|---|
| Train | 70 % of synthetic events generated on venue topologies V1, V2 |
| Validation | 15 % of V1/V2 events (early stopping, conformal calibration) |
| Test-in-venue | 15 % of V1/V2 events (unseen events, seen venues) |
| Test-new-venue | All events on topology V3 (never seen in training) — measures cross-venue generalisation |

Suggested volume: 60 events per topology × 6 h. Exact counts fixed in [experimental_design.md](../RESEARCH/experimental_design.md).

### 8.2 Real data

Real recorded sessions are too few to train on. They are used for (a) CV accuracy evaluation, (b) **test-only** forecasting evaluation of the synthetic-trained model, (c) optionally fine-tuning with leave-one-session-out evaluation. Real and synthetic results are reported in **separate tables**.

### 8.3 Hyper-parameter tuning

- Grouped $K$-fold ($K=5$) by event within the training set (`GroupKFold`), or rolling-origin evaluation within events [41].
- Optuna TPE, 50 trials per (config, horizon) for the median model; quantile models reuse the median's structural parameters.
- XGBoost search space: `max_depth` 3–8, `learning_rate` 0.02–0.2 (log), `n_estimators` up to 2000 with early stopping (50 rounds) on validation, `min_child_weight` 1–20, `subsample` 0.6–1.0, `colsample_bytree` 0.5–1.0, `reg_lambda` 0.1–10 (log).
- LSTM: hidden 32–128, layers 1–2, dropout 0–0.3, lr 1e-4–3e-3, window $W \in \{30, 60\}$; Adam; early stopping on validation pinball loss.
- Fixed seeds; results reported as mean ± std over 5 seeds for LSTM.

## 9. LSTM design (advanced model)

- Input: sequence of the A4 feature vector for the last $W$ minutes for one zone (static features repeated).
- Architecture: 1–2 layer LSTM → dense head with $|\mathcal H| \times |Q| = 9$ outputs.
- Loss: mean pinball loss $\sum_{h,q} \rho_q(y_{i,h} - \hat y^{(q)}_{i,h})$ where $\rho_q(e) = \max(qe, (q-1)e)$ [36].
- Same target normalisation and same splits as XGBoost.

## 10. Graph-based forecasting (extension A5)

Represent all zone signals as a matrix $\mathbf X(t) \in \mathbb R^{|V| \times d}$. An STGCN-style block applies gated temporal convolution, then graph convolution $\sigma(\hat A\, \mathbf X \Theta)$ with normalised adjacency $\hat A = \tilde D^{-1/2}(A+I)\tilde D^{-1/2}$ [47], then temporal convolution again. With $|V| \le 15$ this is a small model trainable on a laptop GPU.

**When it is justified:** only if (i) A4 > A2 shows neighbour information is useful, and (ii) residual analysis shows errors concentrated at times of inter-zone propagation (e.g. after releases). Otherwise the hand-crafted neighbour features already capture what the GNN would learn, at lower cost. This is hypothesis H5.

## 11. Uncertainty estimation

1. Quantile boosters give raw P10/P90.
2. **Split-conformal calibration (CQR)** [37] on validation events: compute conformity scores $E = \max(\hat q_{0.1} - y,\; y - \hat q_{0.9})$, take the $(1-\alpha)(1+1/n)$ empirical quantile $\hat Q$, and widen intervals by $\hat Q$. Target coverage 80 %.
3. Report empirical coverage and mean width on test ([16 §3](16_MODEL_EVALUATION.md)).

Caveat: conformal guarantees assume exchangeability between calibration and test data, which time series and synthetic-to-real shift violate. Coverage is therefore *measured*, not assumed.

## 12. Online inference cycle

```text
every minute at hh:mm:10 for each LIVE event:
  window = observations[t-60 .. t]          # forward-fill gaps <= 3 min; else zone uses fallback
  X = FeatureBuilder.build(window, schedule, graph, t, model.feature_set)
  for h in (5, 15, 30):
      q10, q50, q90 = model.predict(X, h)    # sorted, inverse-transformed, conformal-adjusted
  if error or len(window) < 15 min: use PersistenceForecaster, is_fallback = true
  write predictions; call M7
```

Cold start: during the first 15 minutes of an event, predictions are persistence-based and labelled as such in the UI.

## 13. Model registry and versioning

`model_versions` table + `models/<name>_<version>/` containing boosters, `manifest.json` (feature set, horizons, quantiles, training events hash, metrics, git commit, seed), and conformal offsets. Exactly one version is active per venue (or globally) at a time (FR-FC-05).

## 14. Summary of recommendations

| Question | Recommendation |
|---|---|
| Baseline | Persistence (B0) + moving average, trend, conservation |
| Main model | Global XGBoost, direct multi-horizon, quantile, capacity-normalised delta target, feature set A4 |
| Advanced | Global LSTM with pinball loss |
| Graph | Neighbour features in XGBoost first; GNN only as A5 extension |
| Uncertainty | Quantile + split-conformal calibration |
| Validation | Event-grouped splits; unseen venue topology; real sessions as test-only |

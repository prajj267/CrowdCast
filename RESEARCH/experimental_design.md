# Experimental Design

| Field | Value |
|---|---|
| Version | 0.1.1 |
| Status | Pre-registered plan (fixed before results are seen; deviations must be logged). §1–§11 are unchanged; **§12 lists the deviations of the solo execution** |

---

## 1. Objective

Answer RQ1–RQ6 ([research_questions.md](research_questions.md)) by testing H1–H7 ([research_hypotheses.md](research_hypotheses.md)) through controlled ablations on identical data splits.

## 2. Datasets

| Dataset | Origin | Content | Role |
|---|---|---|---|
| SYN-clean | CROWDSIM, true states as inputs | V1 (8 zones), V2 (10 zones): 60 events each; V3 (12 zones): 60 events | Upper bound on achievable accuracy; isolates feature value |
| SYN-noisy | CROWDSIM + noise model calibrated on our CV errors | Same events as SYN-clean, noisy inputs, true targets | Main synthetic result |
| REAL-staged | Staged volunteer scenario, CV inputs, manual targets | Target ≥ 2 sessions × ≥ 60 min, 3–4 zones | Real-data check (test only) |
| REAL-event | Recorded campus event (if approved) | ≥ 1 session × ≥ 2 h | Real-data check (test only) |

Event durations 4–8 h (synthetic). All synthetic data labelled `SYNTHETIC`.

## 3. Splits

| Split | Events |
|---|---|
| Train | V1: 42, V2: 42 |
| Validation | V1: 9, V2: 9 (early stopping, conformal calibration) |
| Test-in-venue | V1: 9, V2: 9 |
| Test-new-venue | V3: all 60 |
| Real test | All REAL sessions (no training on them in the main study) |

Split assignment by event ID, fixed by seed 2027 and stored in `splits.json` before any model is trained.

## 4. Ablation configurations

| Config | Features | Models |
|---|---|---|
| **A1** | Historical occupancy only (F_HIST) | XGB, RF, LSTM |
| **A2** | F_HIST + inflow/outflow (F_FLOW) | XGB, RF, LSTM |
| **A3** | F_HIST + event schedule (F_SCHED) | XGB, RF, LSTM |
| **A4** | All features: F_HIST + F_FLOW + F_SCHED + neighbour features (F_NBR) | XGB, RF, LSTM |
| **A5** | All features + explicit spatial graph model | STGCN-style GNN (stretch) |
| A4\NBR (control) | F_HIST + F_FLOW + F_SCHED, no neighbours | XGB — needed to isolate H4 |

Baselines B0 (persistence), B1 (moving average), B2 (linear trend), B3 (conservation extrapolation) are evaluated on every dataset and horizon.

Feature definitions: [10 §5](../DOCUMENTATION/10_ML_FORECASTING_METHODOLOGY.md). The brief's ablation list maps as: (1) A1, (2) A2, (3) A3, (4) A4, (5) A5.

## 5. Procedure

1. Generate synthetic events (fixed seeds per event).
2. Build datasets with the shared `FeatureBuilder`; write Parquet with split labels.
3. For each config × model × horizon: tune on train via GroupKFold (5 folds by event) with Optuna (50 trials, XGB/RF; 20 trials, LSTM).
4. Retrain on full train with best parameters; early stopping on validation.
5. Calibrate intervals on validation (split-conformal).
6. Evaluate **once** on each test split; LSTM/GNN over 5 seeds (mean ± std), tree models over 3 seeds.
7. Replay test events through M6 + M7 to compute operational metrics.
8. Repeat steps 2–7 for SYN-clean and SYN-noisy; apply the selected models to REAL data.

## 6. Metrics

Primary: per-event MAE at each horizon. Secondary: RMSE, normalised MAE, peak-period MAE, skill vs B0, pinball loss, coverage, interval width, precision/recall/F1 for ≥ HIGH, warning lead time, false-alarm rate, missed-episode rate. Definitions: [16](../DOCUMENTATION/16_MODEL_EVALUATION.md).

## 7. Statistical analysis

- Unit of analysis: **event** (per-event mean error), because minutes within an event are dependent.
- Paired comparison: Wilcoxon signed-rank over test events (n = 18 in-venue; n = 60 new-venue). One-sided for directional hypotheses H1–H4, H6; two-sided for H5.
- Multiple comparisons: Holm correction across the three horizons within each hypothesis.
- Effect size: median relative MAE reduction with 95 % bootstrap CI (10,000 resamples over events).
- Practical threshold: ≥ 5 % relative MAE reduction (declared in advance).
- Real data: too few sessions for event-level tests; report Diebold–Mariano tests [42] per session and descriptive comparisons, clearly labelled as indicative.

## 8. Stratified analyses

- **Post-release periods**: 30 min after any upstream schedule item ends (H4).
- **Peak periods**: true $u \ge 0.6$.
- *Implementation (7.3.5):* both strata are defined on the forecast **target** minute $t+h$. Post-release uses the *published* schedule of zones upstream in the venue graph (an item end $e$ with $t+h-30 < e \le t+h$), derived from the A4 schedule columns of the upstream zones at issue time. Each per-event row gets the MAE over its stratum minutes (`mae_peak`, `mae_post_release`), and an event with no such minutes is left out of that paired test. The bootstrap CI is the percentile interval. Code: `backend/tools/training/stats.py`, `ablation.py`.
- **By zone type**: corridors vs stages vs food areas.
- **By density band** of CV input quality (REAL).

## 9. Threats to validity

| Threat | Type | Mitigation |
|---|---|---|
| Simulator encodes the hypothesis (schedule drives simulated demand) | Construct | Published-vs-actual schedule perturbation; unscheduled attractions; real-data check; report SYN and REAL separately |
| Hyper-parameter tuning favours one config | Internal | Same tuning budget per config |
| Leakage across minutes/events | Internal | Event-level splits; leakage unit test TC-ML-02 |
| Few real sessions | External / statistical | Real results labelled indicative |
| Single noise model | External | Sensitivity run with 2× noise |
| Researcher degrees of freedom | Internal | This plan fixed before results; deviations logged in `EXPERIMENT_LOG.md` |

## 10. Expected contributions (conditional on execution)

1. A reproducible venue-zone forecasting pipeline from video to alerts.
2. Quantified evidence (positive or negative) on the value of schedule and neighbour features at venue scale, per horizon.
3. Quantified effect of perception error on forecast accuracy.
4. An open synthetic event dataset generator with documented assumptions.

## 11. Compute budget

Tree models: minutes per config on a laptop CPU. LSTM: < 1 h per config on a 6 GB GPU (estimate). Full ablation (≈ 5 configs × 3 models × 3 horizons × seeds) is expected to fit in 1–2 days of machine time; estimates are verified in week 6.

## 12. Deviations in the solo execution (added 2026-11-23, 9.4 audit F-RES)

The plan above is left as pre-registered. The project is executed by one developer on a CPU-only laptop with public datasets only (WORKFLOW decisions D2, D6). Each change below is recorded, with its reason, in the WORKFLOW Deviation log; this section only points to them so that a reader of this plan sees them.

| Section | Pre-registered | Executed | Logged |
|---|---|---|---|
| §2 Datasets, §3 Real test | REAL-staged and REAL-event datasets as a real-data test | **Dropped** (D6: no own recordings). There is no REAL forecasting dataset; all forecasting results are SYNTHETIC evidence. REAL public data (Mall, ShanghaiTech B, MOT20) is used only for CV evaluation and to calibrate the SYN-noisy noise model | 2026-11-20 |
| §5 step 3 | Optuna 50 trials, GroupKFold 5 folds | 20 trials, 3 folds per (config, horizon), same budget for every config; median model tuned, quantile models reuse its parameters | 2026-11-21 |
| §5 step 7 | Replay test events through the running M6 + M7 | Offline replay of the saved forecasts through the real M7 state machine (`risk.alerts.decide`); the database and API are bypassed | 2026-11-22 |
| §5 step 8, §7 last bullet, §8 last bullet | Apply selected models to REAL data; Diebold–Mariano per real session; density bands of REAL CV input | Not applicable (no REAL forecasting data). Density bands are reported for the CV evaluation only, by true count where no calibrated areas exist | 2026-11-20, 2026-11-21 |
| §4 Models | XGBoost, RF, LSTM; A5 GNN | XGBoost quantile models and baselines B0–B3; RF optional; LSTM and A5 are gated extensions, not started | WORKFLOW scope table, Extensions |
| §9 Threats | "Real-data check" mitigates the simulator-encodes-hypothesis threat | Not available. Remaining mitigations: published-vs-actual schedule perturbation, separate SYN-clean / SYN-noisy reporting, and stating the limitation in the report. The 2× noise sensitivity run has **not yet been run** | — |
| §11 Compute | LSTM on a 6 GB GPU | No GPU; LSTM not started | D6/AS4 |

Splits (§3), the statistical analysis (§7, except the REAL bullet), the strata (§8) and the metrics (§6) are executed as pre-registered; `configs/splits.json` (seed 2027) was frozen before the first training run.

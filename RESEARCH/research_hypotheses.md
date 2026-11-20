# Research Hypotheses

All hypotheses are **untested**. They are stated so that they can be rejected. "Improve" means lower per-event MAE on the test events, tested with a one-sided Wilcoxon signed-rank test over test events at α = 0.05 with Holm correction across horizons (details in [experimental_design.md](experimental_design.md)). An effect is considered *practically meaningful* if the median relative MAE reduction is ≥ 5 % — a threshold chosen in advance to avoid declaring trivially small gains.

| ID | Hypothesis (H₁) | Null (H₀) | Test | Notes / why we expect it |
|---|---|---|---|---|
| H1 | Schedule features improve forecasts over history-only models, with the largest gain at 15 and 30 min | A3 MAE ≥ A1 MAE | A3 vs A1 per horizon | Releases and start times are known in advance; history alone cannot anticipate a surge that has not started. Risk: synthetic simulator uses the schedule, so gain may be inflated — mitigated by schedule perturbation and real-data check |
| H2 | Inflow/outflow features improve forecasts over history-only models, mainly at 5 min | A2 MAE ≥ A1 MAE | A2 vs A1 | Net flow is the derivative of occupancy (conservation); its information decays with horizon |
| H3 | All learned models beat persistence at 15 and 30 min, but skill over persistence at 5 min is small | Skill ≤ 0 at 15/30 min | Skill score vs B0 with bootstrap CI | Short-horizon occupancy is highly autocorrelated |
| H4 | Neighbour features improve forecasts beyond own-zone features (A4 < best of A2, A3), especially during the 30 min after a scheduled release in an upstream zone | A4 MAE ≥ min(A2, A3) MAE | A4 vs union model without F_NBR; stratified by "post-release" periods | Upstream outflow precedes downstream inflow by travel time |
| H5 | An explicit spatiotemporal GNN does **not** significantly outperform XGBoost with graph-derived features at venue scale (≤ 15 zones) | — (this is a two-sided equivalence-style question) | A5 vs A4, two-sided Wilcoxon; report effect size and CI | Small graphs and limited data favour engineered features. Stated as expected direction; either outcome is informative |
| H6 | Under realistic perception noise, forecast error increases, but the ranking A4 ≤ A3 ≤ A1 is preserved | Ranking changes or gains vanish | Repeat ablation on SYN-noisy and REAL | Tests robustness of conclusions to CV error |
| H7 | Conformal-calibrated 80 % intervals achieve 75–85 % empirical coverage on unseen synthetic events, but under-cover on real data | Coverage outside 75–85 % on synthetic | Empirical coverage with bootstrap CI | Exchangeability holds approximately within synthetic distribution; synthetic-to-real shift breaks it |

## What would count as a negative result

- H1 rejected on real data while accepted on synthetic data → evidence that the simulator over-represents schedule effects.
- H4 rejected → venue topology adds little at this scale; independent zone models plus schedule are sufficient.
- H3 rejected at 30 min → 30-min forecasts are not reliable enough to justify alerts at that horizon.

Negative results are reported with the same prominence as positive ones.

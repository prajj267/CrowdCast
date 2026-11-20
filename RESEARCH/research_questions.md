# Research Questions

## Research direction

**Event-Aware Spatiotemporal Crowd Congestion Forecasting Across Interconnected Venue Zones**

## Research problem

Crowd forecasting at event venues has two sources of predictable structure that independent zone-wise time-series models ignore:

1. **The event programme.** Demand is driven by scheduled items (performances, meals, exit waves) that are published in advance.
2. **The venue topology.** People leaving one zone arrive in neighbouring zones after a travel delay, so congestion propagates along the venue graph.

Prior work shows that external covariates and graph structure help in citywide and road-network forecasting with abundant data [19]–[24]. It is not established — at venue scale, with camera-derived zone counts, a handful of zones and only hours of data per event — **whether** and **by how much** schedule and neighbour information improve short-horizon congestion forecasts and early warnings, and how much of any benefit survives realistic perception error.

## Primary question

**RQ0.** Does incorporating event-schedule features and neighbouring-zone states improve 5-, 15- and 30-minute zone occupancy forecasts and congestion warnings, compared with independent zone-wise models using only each zone's own history?

## Sub-questions

| ID | Question | Comparison | Hypothesis |
|---|---|---|---|
| RQ1 | Do **event-schedule** features reduce forecast error relative to history-only models? | A3 vs A1 | H1 |
| RQ2 | Do measured **inflow/outflow** features reduce forecast error relative to history-only models? | A2 vs A1 | H2 |
| RQ3 | How do forecast skill (vs persistence) and the benefit of contextual features vary with **horizon** (5/15/30 min)? | All configs × horizons | H3 |
| RQ4 | Do **neighbouring-zone** (graph-derived) features add value beyond own-zone flow and schedule features, especially during propagation periods? Does an explicit **GNN** add value beyond graph-derived features? | A4 vs A2+A3 union; A5 vs A4 | H4, H5 |
| RQ5 | How does **perception error** (CV counting/flow error) propagate into forecast error, and do feature-group gains persist under realistic noise? | Clean vs noisy inputs; synthetic vs real | H6 |
| RQ6 | Are **prediction intervals** from quantile boosting with conformal calibration well calibrated on unseen events and on real data? | Empirical coverage vs nominal 80 % | H7 |

## Operational question (cross-cutting)

**RQ-OP.** For a fixed false-alarm budget, which configuration maximises median warning lead time while keeping the missed-episode rate low? (Evaluated with metrics in [16 §5](../DOCUMENTATION/16_MODEL_EVALUATION.md).)

## Outstanding questions not addressed by the experiments

- How do operators actually use forecasts, and what lead time is operationally sufficient? (Needs user studies with organisers.)
- Do recommendations based on forecasts change crowd behaviour (feedback effects)?
- How do findings transfer to very dense crowds (> 3 persons/m²) that our data are unlikely to contain?

References: [RESEARCH/bibliography.md](bibliography.md).

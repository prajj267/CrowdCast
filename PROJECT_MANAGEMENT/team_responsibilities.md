# Team Responsibilities

> **Solo project (WORKFLOW 0.3.3).** CROWDCAST is built by **one developer**, who holds every role below. The role table is kept as the original team plan and as a map of which modules belong together. Review by a second team member, weekly meetings and pairing do not apply; the solo definition of done is in `CLAUDE.md §8`, and progress is tracked in [`WORKFLOW.md`](../WORKFLOW.md). Effort estimates in person-days are team-plan figures, not solo measurements.

## Roles (4-member team)

| Role | Owns modules | Primary responsibilities | Secondary | Approx. load (pd, from task breakdown) |
|---|---|---|---|---|
| **CV lead** | M1, M2, M3 | Video ingestion, detection, tracking, regions/lines, minute aggregation; recording protocol and ethics application; annotation coordination; CV evaluation | Helps ML with noise-model calibration and ablation runs in weeks 6–7 | ≈ 20 |
| **ML lead** | M6, T1 (CROWDSIM), T2 | Simulator, feature builder, baselines, XGBoost, LSTM, conformal calibration, ablation study, statistics | Owns research documents (RQs, hypotheses, experimental design) | ≈ 30–34 (highest; CV lead offloads ablation execution) |
| **Backend & data lead** | M4, M5, M7, M8 | Schema, migrations, API, auth/RBAC, graph validation, risk engine and alerts, retention, performance, security review, deployment | CI/CD and Docker ownership | ≈ 28 |
| **Frontend & integration lead** | M9 | Design system, all pages, API client, E2E tests, demo script | Annotation support; integration testing across modules | ≈ 31 |

Every member writes tests for their own code and reviews at least one other member's pull requests each week.

## RACI for key deliverables

R = Responsible, A = Accountable, C = Consulted, I = Informed.

| Deliverable | CV | ML | BE | FE |
|---|---|---|---|---|
| DB schema & API contracts | C | C | **A/R** | C |
| Ingestion contract (observation JSON) | R | C | **A** | I |
| CV pipeline & CV evaluation | **A/R** | I | C | I |
| CROWDSIM & synthetic datasets | C | **A/R** | I | I |
| Forecasting models & ablations | C | **A/R** | I | I |
| Risk engine & alerts | I | C | **A/R** | C |
| Dashboard | I | C | C | **A/R** |
| Ethics approval & recording | **A/R** | I | I | C |
| Security & privacy controls | C | I | **A/R** | C |
| Final report | R | **A/R** | R | R |
| Demo | R | R | R | **A/R** |

## Working agreements

- **Cadence:** 15-min stand-up 3×/week; weekly 1-h review with demo of the current increment; milestone review with supervisor at MS1–MS5.
- **Branching:** trunk-based; short-lived feature branches; PR with requirement IDs; one approving review; CI green before merge.
- **Contracts first:** changes to DB schema, API schemas or the observation contract require a PR updating [13](../DOCUMENTATION/13_DATABASE_DESIGN.md)/[14](../DOCUMENTATION/14_API_SPECIFICATION.md) and notice to all members.
- **Experiment log:** ML lead maintains `EXPERIMENT_LOG.md` (date, config, data, seed, result path, deviation from plan).
- **Results integrity:** no numbers enter the report or documentation unless produced by committed code from a logged run.

## 3-member team variant

| Role | Merged responsibilities |
|---|---|
| CV + data collection | CV lead as above, plus annotation |
| ML + research | ML lead as above (LSTM only if ahead of schedule) |
| Full-stack | Backend + frontend; frontend scope reduced to Live, Prediction, Alerts, minimal Event/Venue forms with YAML import instead of polygon editor |

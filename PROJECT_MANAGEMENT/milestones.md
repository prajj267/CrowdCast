# Milestones

Milestone IDs use `MS` to avoid confusion with module IDs (M1–M9). Weeks are relative to project start (see [21_DEVELOPMENT_ROADMAP.md](../DOCUMENTATION/21_DEVELOPMENT_ROADMAP.md)).

| ID | Week (end) | Milestone | Deliverables | Acceptance (demonstrable) |
|---|---|---|---|---|
| MS0 | 0 | Documentation baseline | This documentation package | Team review sign-off; open questions ([INDEX §7](../DOCUMENTATION/INDEX.md#7-outstanding-questions)) answered |
| MS1 | 1 | Foundations | Repo, CI (lint/type/test), Docker Compose, DB schema v1 + migrations, auth skeleton, CROWDSIM design note, ethics application submitted | `docker compose up` on every member's machine; CI green; login works via API |
| MS2 | 3 | **Vertical slice** | Venue/zone/event CRUD; CROWDSIM v1 (V1); observation ingestion; persistence prediction cycle; M7 levels; minimal live page; CV worker producing per-frame counts on a sample clip | Replaying a synthetic event changes zone colours on the live page every minute; persistence predictions in DB |
| MS3 | 5 | **Core prototype** | CV regions/lines + minute aggregation posting REAL observations; feature builder A1–A4; XGBoost quantile model; alerts with hysteresis; live monitoring + prediction pages; CROWDSIM v2 (V2, V3, noise); staged recording done | A scripted synthetic surge raises a PREDICTED alert before the CURRENT alert; a recorded clip produces REAL observations end to end |
| MS4 | 7 | **Evaluation** | Annotations; CV evaluation tables; ablation A1–A4 (SYN-clean, SYN-noisy, REAL); operational metrics; history + alerts pages; LSTM if gate met | All tables in [16](../DOCUMENTATION/16_MODEL_EVALUATION.md) filled from pipeline output; statistical tests run |
| MS5 | 8 | **Final demo & report** | E2E and performance tests, hardened deployment, documentation updated with real results, report, presentation, recorded demo | Demo runs on a clean machine following [18 §5](../DOCUMENTATION/18_DEPLOYMENT_PLAN.md); report cites only pipeline-produced results |
| MS6 (optional) | 9–10 | Extensions | A5 GNN, density-map fallback, or RTSP | Gate criteria met; reported as extension |

## Gate criteria for extensions

| Extension | Start only if |
|---|---|
| LSTM | MS3 met and XGBoost A4 evaluated on SYN-noisy |
| GNN (A5) | LSTM done or skipped, ≥ 1 week remaining, and A4 shows a neighbour-feature gain worth explaining |
| Density-map counter | CV evaluation shows a dense-band undercount that affects alerts |
| RTSP live | Recorded pipeline stable for a 2-h replay without errors |

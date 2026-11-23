# Risk Register

Scales: Likelihood (L) and Impact (I) 1 = low … 5 = high; Score = L × I. Reviewed weekly; owner updates status.

| ID | Risk | Category | L | I | Score | Mitigation | Contingency (if it occurs) | Owner | Trigger / indicator |
|---|---|---|---|---|---|---|---|---|---|
| R1 | Person detector undercounts badly in dense zones | Technical (CV) | 4 | 4 | 16 | Elevated cameras; density flag; evaluate by density band early (week 3 spot check) | Density-map fallback for flagged regions; restrict claims to tested density range | CV | Dense-band relative MAE high on first annotated set |
| R2 | Too little real data for meaningful evaluation | Data | 4 | 4 | 16 | Staged volunteer scenario planned early; synthetic data as primary experimental basis | Report real-data results as indicative only; strengthen synthetic sensitivity analysis | CV | Approval or volunteers not confirmed by week 3 |
| R3 | Synthetic-to-real gap invalidates conclusions | Research | 3 | 5 | 15 | Schedule perturbation, noise model calibrated on real CV errors, separate reporting | State limitation explicitly; frame findings as synthetic evidence | ML | Synthetic-trained model fails to beat persistence on REAL |
| R4 | Ethics/recording permission delayed or refused | Compliance | 3 | 4 | 12 | Apply in week 1; staged scenario needs less approval than public event | Use public datasets (Mall, MOT20) for CV + synthetic for forecasting | CV | No response by week 3 |
| R5 | CV pipeline integration slips and blocks everything | Schedule | 3 | 4 | 12 | AD-02: single ingestion contract; CROWDSIM unblocks backend/ML/FE | Demo on synthetic + pre-processed observations | BE | MS2 slice not working by end of week 3 |
| R6 | No GPU available / CUDA setup issues on Windows | Infrastructure | 3 | 3 | 9 | Identify GPU machine in week 1; native venv option | Offline CPU processing of recordings; replay observations | CV | CV env not working by end of week 1 |
| R7 | Data leakage inflates results | Research | 2 | 5 | 10 | Event-level splits, leakage unit test, shared FeatureBuilder, pre-registered design | Re-run affected experiments; disclose | ML | Suspiciously large gains; leakage test fails |
| R8 | Scope creep (GNN, RTSP, route optimisation) | Schedule | 4 | 3 | 12 | Gate criteria in milestones; core/extension separation | Drop extensions | All | Extension work before MS3 |
| R9 | Team member unavailable (exams, illness) | People | 3 | 3 | 9 | Pairing on critical modules; documentation; 12 % contingency | 3-member variant scope | All | > 3 days absence |
| R10 | AGPL-3.0 licence incompatible with institution policy | Legal | 2 | 3 | 6 | Check policy in week 1; detector behind interface | Switch to YOLOX (Apache-2.0) | CV | Policy response |
| R11 | Dataset licence terms prevent intended use | Legal | 2 | 2 | 4 | Read terms before download; use only for academic evaluation | Drop dataset; use alternatives | CV | Terms review |
| R12 | Video/clock desynchronisation corrupts flows | Technical | 2 | 3 | 6 | Clap/clock sync, offsets per camera, deterministic event time | Manual offset correction from visible clock | CV | Venue-level conservation check violated |
| R13 | Alert flapping / too many false alarms undermines demo | Product | 3 | 3 | 9 | Hysteresis, 2-cycle confirmation, operational metrics | Raise thresholds for PREDICTED alerts; tune on validation | BE | > 6 false alarms/hour on validation replay |
| R14 | Privacy incident (footage leaked) | Compliance | 1 | 5 | 5 | Encrypted storage, access list, no footage in repo | Incident report to institution; delete affected data | CV | Any unauthorised copy |
| R15 | Frontend effort underestimated (polygon editors) | Schedule | 3 | 3 | 9 | Use YAML import as fallback for configuration | Ship YAML import, editors later | FE | T3.9 > 6 pd |
| R16 | Documentation diverges from implementation | Quality | 3 | 2 | 6 | "Contracts first" rule; docs updated in same PR | Consistency audit before MS5 | BE | PRs changing contracts without doc changes |

## Top risks (score ≥ 12)

R1, R2, R3, R4, R5, R8 — reviewed at every weekly meeting.

## Solo status (2026-11-23, updated 2026-11-24; WORKFLOW 0.3.3)

One developer owns every risk; the Owner column above is the team plan. Status as of this date:

| ID | Status | Note |
|---|---|---|
| R1 | **Occurred** | Public-data CV evaluation shows systematic undercounting that grows with density (`EXPERIMENT_LOG.md`, Phase 7.1). Claims are limited to the tested ranges; the density-map extension is gated and not started |
| R2 | **Occurred by decision** (D6) | No own recordings: no REAL forecasting dataset. Forecasting conclusions are synthetic evidence; REAL data is used for CV evaluation only |
| R3 | Accepted limitation | Noise model calibrated on public-data CV errors; SYN-clean and SYN-noisy reported separately; stated in the report |
| R4 | Avoided (D6) | No recording, so no permission needed |
| R5 | Did not occur | MS2 and MS3 met (WORKFLOW status table) |
| R6 | **Occurred** | No NVIDIA GPU. Contingency applied: offline CPU processing of recorded clips; the demo replays stored observations |
| R7 | Mitigated | Event-level frozen splits (seed 2027), leakage tests, one shared feature builder, tuning inside training events only |
| R8 | Controlled | Extensions are gated in `WORKFLOW.md`; none started |
| R9 | **Changed**: "single developer unavailable" | No team to cover absence. Mitigation: no hard deadline (D5); the WORKFLOW session log and `CLAUDE.md` let work resume after a break |
| R10 | Avoided (D2) | YOLOX (Apache-2.0) chosen from the start; no Ultralytics |
| R11 | Open | Licence terms of Mall, ShanghaiTech B and MOT20 still to be read at the source (WORKFLOW 0.2.2) |
| R12 | Largely not applicable | No own multi-camera recordings; event time comes from the configured start |
| R13 | **Measured** (WORKFLOW 7.4.2) | False alarms and lead time per model, split and dataset are in `EXPERIMENT_LOG.md` and [16 §9](../DOCUMENTATION/16_MODEL_EVALUATION.md). On some test configurations the learned model raises more false alarms per hour than B0; the report states this |
| R14 | Mitigated | No own footage; public data in git-ignored folders; `scripts/privacy_check.sh` over the whole history, also in CI |
| R15 | Avoided | YAML import from the start; no polygon editor |
| R16 | **Occurred** | Found and fixed in the 9.4 audit ([AUDIT_9_4.md](../DOCUMENTATION/AUDIT_9_4.md)); CI now fails when the generated API client drifts from the backend |

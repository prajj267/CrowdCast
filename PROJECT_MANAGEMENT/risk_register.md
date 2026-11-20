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

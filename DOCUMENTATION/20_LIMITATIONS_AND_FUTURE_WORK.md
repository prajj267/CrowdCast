# 20 — Limitations and Future Work

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Anticipated limitations of the proposed design (to be updated with measured evidence) |

---

## 1. Limitations

| # | Limitation | Effect on CROWDCAST | Mitigation in prototype | Residual risk |
|---|---|---|---|---|
| L1 | **Occlusion** | People hidden behind others are not detected → undercount, fragmented tracks, missed crossings | Elevated cameras, ByteTrack low-score association, per-minute median, LOW_CONFIDENCE flag | Systematic undercount in dense zones |
| L2 | **Camera blind spots** | Unobserved areas and boundaries break both occupancy estimates and conservation | Coverage fraction $\kappa$, graph validation warns about edges without lines, unobserved zones flagged | Coverage correction assumes uniform density — often false (e.g. near a stage barrier) |
| L3 | **Inaccurate person detection** | COCO-trained detectors miss small/distant people; false positives on posters, mannequins | Class filter, region masks, density-band evaluation, optional density-map model | Counts are estimates with measured but non-zero error |
| L4 | **Camera calibration** | Without homography, speeds are in pixels and density per m² relies on approximate areas | Speed optional; areas from floor plan | $v_i$ unavailable for many cameras; density approximate |
| L5 | **Domain shift across venues** | Lighting, angle, weather, crowd type differ from training/evaluation footage; forecasting behaviour differs by venue | Global model with zone-type features; held-out topology V3 test | A new venue may need recalibration and new data |
| L6 | **Limited training data** | Few real events; deep models likely overfit | Synthetic data; gradient boosting; strong baselines | Conclusions may not hold for real events |
| L7 | **Synthetic-to-real generalisation** | Simulator assumptions (choice model, speed–density relation) shape what the model learns; schedule effects may be exaggerated | Schedule perturbation, parameter randomisation, noise model calibrated on real CV errors, separate reporting | Synthetic gains may not transfer — explicitly tested |
| L8 | **Uncertain event attendance** | Expected attendance is a guess; turnout varies with weather, lineup | Attendance only as a weak feature; model relies on observed recent dynamics | Large surprises (no-show headliner) remain hard |
| L9 | **Unpredictable pedestrian behaviour** | Spontaneous gatherings, rain shelters, incidents, rumours | Short horizons, CURRENT alerts independent of forecasts, uncertainty intervals | Rare events are inherently poorly predicted |
| L10 | **Clock and sync errors** | Misaligned cameras distort flows between zones | Event time from configured offsets; clap/clock sync in protocol | ± few seconds error — negligible at 1-min buckets if protocol followed |
| L11 | **Short events / cold start** | First 15 min lack history | Persistence fallback labelled in UI | Early-event forecasts weaker |
| L12 | **Thresholds are organiser-defined** | Wrong capacity values produce wrong levels | Validation, display of raw density | Garbage-in, garbage-out |
| L13 | **Not a safety system** | Must not replace stewarding, crowd safety plans or CCTV operators | Documentation and UI wording | — |

## 2. Future work

| Area | Description | Prerequisite |
|---|---|---|
| Multi-camera fusion | Project detections from all cameras to a common ground plane via homographies; de-duplicate by position; estimate occupancy over the union of views | Calibrated cameras with overlap |
| Graph neural networks | STGCN / Graph WaveNet over venue graphs, possibly pre-trained across many synthetic venues; compare against feature-based XGBoost (A5) | Larger dataset; positive A4 result |
| Real-time edge inference | Run detection on edge devices next to cameras, transmitting only counts — better privacy and bandwidth | Hardware budget |
| Density-map hybrid | Automatic switching between detection and density-map counting by estimated density; flows from optical flow in dense regions | Annotated dense footage |
| Mobile operator application | Push alerts to stewards' phones with zone context | Notification service, auth on mobile |
| Multi-event / multi-venue support | Concurrent live events, per-venue models, organisation tenancy | Scheduler and API changes |
| Route optimisation | Congestion-aware routing for stewards' guidance; evaluation by simulation for side-effects ([11 §8](11_SPATIAL_INTELLIGENCE.md)) | Reliable 15–30-min forecasts |
| Online learning | Update models during an event from new observations (e.g. residual correction) | Stable base model |
| Crowd-pressure indicators | Velocity-variance based risk signals [30] | Calibrated speed estimates |
| Additional sensors | Wi-Fi/BLE or ticket-scan entries as extra inputs [26]–[28] | Data access agreements |
| Causal evaluation of interventions | Measure whether alerts led to actions that reduced congestion | Partnership with organisers |

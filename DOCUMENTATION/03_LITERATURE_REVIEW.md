# 03 — Literature Review

| Field | Value |
|---|---|
| Version | 0.1 |
| Status | Structured review for project design; to be extended by the team |

---

## 0. Method and reliability statement

- **Search scope.** IEEE Xplore, ACM Digital Library, CVF Open Access, Springer, Elsevier, arXiv, and dataset home pages. Searches combined the terms *crowd counting, density estimation, pedestrian tracking, crowd flow prediction, spatiotemporal graph forecasting, event-aware forecasting, crowd early warning*.
- **Verification.** Each entry carries a verification tag:
  - **[V]** — existence, authors, venue and year were confirmed against an online source during preparation of this document.
  - **[K]** — taken from established reference knowledge of a widely cited paper; bibliographic details are believed correct but **must be checked against the PDF before submission** (checklist in [bibliography.md](../RESEARCH/bibliography.md)).
- **Results.** Reported numbers are *as reported by the original authors* on *their* datasets. They are not CROWDCAST results and are not directly comparable across rows. Where we were not certain of an exact figure, we describe the result qualitatively rather than risk a wrong number.
- **Interpretation.** The "Relevance to CROWDCAST" row is our interpretation, clearly separated from the paper's own claims.

---

## 1. Crowd counting and density estimation

### 1.1 MCNN and the ShanghaiTech dataset [1] — [K]

| Field | Content |
|---|---|
| Title | Single-Image Crowd Counting via Multi-Column Convolutional Neural Network |
| Authors | Y. Zhang, D. Zhou, S. Chen, S. Gao, Y. Ma |
| Year / Venue | 2016 / IEEE CVPR |
| Problem | Count people in a single image with arbitrary density and perspective |
| Methodology | Three CNN columns with different receptive-field sizes regress a density map; count = integral of the map. Ground-truth maps from head points with geometry-adaptive Gaussian kernels |
| Dataset | Introduced ShanghaiTech Part A (dense, internet images) and Part B (sparser, Shanghai streets); also UCF_CC_50 |
| Results reported | Improved MAE/MSE over prior regression and CNN baselines on all evaluated sets (see paper tables) |
| Limitations | Single images, no temporal reasoning; columns learn redundant features (later criticised by [2]); density maps give no identities or flows |
| Relevance | Established the density-map paradigm that remains the reference for dense crowds; ShanghaiTech Part B resembles elevated campus cameras and is a candidate for CV evaluation |

### 1.2 CSRNet [2] — [K]

| Field | Content |
|---|---|
| Title | CSRNet: Dilated Convolutional Neural Networks for Understanding the Highly Congested Scenes |
| Authors | Y. Li, X. Zhang, D. Chen |
| Year / Venue | 2018 / IEEE CVPR |
| Problem | Accurate density maps in highly congested scenes |
| Methodology | VGG-16 front end followed by dilated convolutions to enlarge receptive field without losing resolution; single column |
| Dataset | ShanghaiTech A/B, UCF_CC_50, WorldExpo'10, UCSD, TRANCOS (vehicles) |
| Results reported | Lower MAE than MCNN and other contemporaries on ShanghaiTech and other benchmarks (see paper tables) |
| Limitations | Image-level only; computationally heavier than detectors at low density; no localisation of individuals |
| Relevance | A practical pre-trained density model for **dense zones** where detectors fail; candidate fallback counter (extended scope) |

### 1.3 Composition loss and UCF-QNRF [3] — [K]

| Field | Content |
|---|---|
| Title | Composition Loss for Counting, Density Map Estimation and Localization in Dense Crowds |
| Authors | H. Idrees, M. Tayyab, K. Athrey, D. Zhang, S. Al-Maadeed, N. Rajpoot, M. Shah |
| Year / Venue | 2018 / ECCV |
| Problem | Counting, density estimation and localisation jointly in extremely dense crowds |
| Methodology | Loss that decomposes counting into density maps at several kernel widths, encouraging localisation |
| Dataset | Introduced UCF-QNRF (1,535 high-resolution, very dense images) |
| Results reported | State of the art on UCF-QNRF at the time (see paper) |
| Limitations | Extreme densities rarely seen at college events; images not video |
| Relevance | Dataset useful for stress-testing counting at the high end; reminds us that density in our setting may be far lower |

### 1.4 Bayesian loss [6] and DM-Count [7] — [K]

| Field | Bayesian Loss [6] | DM-Count [7] |
|---|---|---|
| Title | Bayesian Loss for Crowd Count Estimation With Point Supervision | Distribution Matching for Crowd Counting |
| Authors | Z. Ma, X. Wei, X. Hong, Y. Gong | B. Wang, H. Liu, D. Samaras, M. Hoai Nguyen |
| Year / Venue | 2019 / ICCV | 2020 / NeurIPS |
| Problem | Avoid hand-designed Gaussian ground-truth maps | Same; theoretical issues with Gaussian smoothing |
| Methodology | Expected-count supervision from point annotations via a Bayesian likelihood | Optimal-transport loss between predicted and ground-truth distributions + count and TV losses |
| Datasets | UCF-QNRF, ShanghaiTech, UCF_CC_50 | UCF-QNRF, NWPU-Crowd, ShanghaiTech, UCF_CC_50 |
| Results | Improved over Gaussian-map training on reported benchmarks | Improved over [6] on reported benchmarks |
| Limitations | Image-level; no tracking | Image-level; OT loss adds training cost |
| Relevance | Public pre-trained weights exist for these families; the team will **not** retrain counting networks — only evaluate pre-trained ones on our footage if the dense-zone fallback is needed |

### 1.5 P2PNet [8] — [K]

| Field | Content |
|---|---|
| Title | Rethinking Counting and Localization in Crowds: A Purely Point-Based Framework |
| Authors | Q. Song *et al.* (full author list to be copied from the paper — see bibliography checklist) |
| Year / Venue | 2021 / ICCV |
| Problem | Count and localise individuals as points rather than boxes or density maps |
| Methodology | Directly predicts a set of head points; one-to-one Hungarian matching for training |
| Datasets | ShanghaiTech A/B, UCF_CC_50, UCF-QNRF, NWPU-Crowd |
| Results | Competitive counting and new localisation metric (see paper) |
| Limitations | Points, not boxes — standard box-based trackers need adaptation |
| Relevance | Bridges counting and localisation; a future option for tracking in dense scenes via point tracking |

### 1.6 JHU-CROWD++ [4] — [V]

| Field | Content |
|---|---|
| Title | JHU-CROWD++: Large-Scale Crowd Counting Dataset and a Benchmark Method |
| Authors | V. A. Sindagi, R. Yasarla, V. M. Patel |
| Year / Venue | 2022 (online 2020) / IEEE TPAMI |
| Problem | Lack of large, diverse, weather/illumination-varied counting data |
| Methodology | Dataset of 4,372 images, 1.51 M head annotations with image-level labels (weather, distractors); benchmark network with residual error estimation |
| Dataset | JHU-CROWD++ (verified on project site: academic and non-commercial use) |
| Results | Benchmark comparisons across many methods (see paper) |
| Limitations | Still single images; non-commercial licence |
| Relevance | Best public source for evaluating **robustness** (rain, night) of counting; usable for academic project |

### 1.7 Mall dataset / localised counting [9] — [V]

| Field | Content |
|---|---|
| Title | Feature Mining for Localised Crowd Counting |
| Authors | K. Chen, C. C. Loy, S. Gong, T. Xiang |
| Year / Venue | 2012 / BMVC |
| Problem | Counting in *local regions* of a scene rather than the whole image |
| Methodology | Multi-output regression from hand-crafted features of local regions, exploiting spatial correlation between regions |
| Dataset | Introduced the Mall dataset: 2,000 consecutive frames from a shopping-mall webcam with > 60,000 labelled pedestrians (verified on dataset page) |
| Results | Improved localised counting over independent per-region regressors (see paper) |
| Limitations | Pre-deep-learning features; one fixed scene; short duration |
| Relevance | Two direct lessons: (1) **region-level counting** is the right abstraction for zones; (2) **correlation between neighbouring regions** helps — an early instance of the spatial-coupling idea CROWDCAST tests for forecasting. The Mall video sequence is also usable as a short temporal test clip |

### 1.8 Surveys [44] — [K]

Sindagi & Patel [44] survey CNN-based single-image counting up to 2017; the NWPU-Crowd paper [5] provides a later large benchmark (5,109 images). These are used for orientation, not for specific claims.

---

## 2. Pedestrian detection and tracking

### 2.1 YOLO [12], Ultralytics YOLO11 [13] — [K]/[V]

| Field | Content |
|---|---|
| Title | You Only Look Once: Unified, Real-Time Object Detection [12]; Ultralytics YOLO11 (software) [13] |
| Authors | J. Redmon, S. Divvala, R. Girshick, A. Farhadi [12]; G. Jocher, J. Qiu [13] |
| Year / Venue | 2016 / CVPR [12]; 2024 / software release, AGPL-3.0 or enterprise licence [13] (licence verified on docs page) |
| Problem | Real-time object detection |
| Methodology | Single-stage detection; YOLO11 adds modern backbone/neck designs and integrated tracking (`model.track`) |
| Dataset | COCO (person is one of 80 classes) |
| Results | Real-time speed on GPU (see model card) |
| Limitations | COCO-trained detectors under-detect small, heavily occluded people; AGPL licence obligations if distributed |
| Relevance | **Recommended starting detector** (`yolo11n`/`yolo11s`) for sparse-to-moderate density |

### 2.2 SORT [14] and DeepSORT [15] — [K]

| Field | Content |
|---|---|
| Title | Simple Online and Realtime Tracking [14]; Simple Online and Realtime Tracking with a Deep Association Metric [15] |
| Authors | A. Bewley, Z. Ge, L. Ott, F. Ramos, B. Upcroft [14]; N. Wojke, A. Bewley, D. Paulus [15] |
| Year / Venue | 2016 / ICIP; 2017 / ICIP |
| Problem | Online multi-object tracking by detection |
| Methodology | Kalman filter motion model + Hungarian assignment on IoU [14]; adds appearance embedding [15] |
| Dataset | MOT benchmarks |
| Results | Real-time tracking competitive with offline methods (see papers) |
| Limitations | [14] suffers ID switches under occlusion; [15] uses appearance embeddings, which have privacy implications |
| Relevance | Conceptual basis. CROWDCAST prefers motion-only association (no appearance features) for privacy |

### 2.3 ByteTrack [16] — [K]

| Field | Content |
|---|---|
| Title | ByteTrack: Multi-Object Tracking by Associating Every Detection Box |
| Authors | Y. Zhang, P. Sun, Y. Jiang, D. Yu, F. Weng, Z. Yuan, P. Luo, W. Liu, X. Wang |
| Year / Venue | 2022 / ECCV |
| Problem | Occluded objects produce low-confidence detections that standard trackers discard, causing fragmented tracks |
| Methodology | Two-stage association: match high-score boxes first, then associate remaining tracks with **low-score** boxes; Kalman motion model; no appearance model required |
| Dataset | MOT17, MOT20, HiEve, BDD100K |
| Results | Reported state-of-the-art MOTA/IDF1/HOTA on MOT17 and MOT20 at publication, at real-time speed (see paper) |
| Limitations | Relies on detector quality; still loses identity under long occlusions |
| Relevance | **Recommended tracker.** Motion-only association suits privacy goals; built into Ultralytics and the `supervision` library |

### 2.4 MOT20 [17] and CrowdHuman [18] — [K]

MOT20 provides crowded pedestrian tracking sequences; CrowdHuman provides heavily occluded person boxes (full, visible and head boxes). Both are **evaluation** resources for our detector/tracker in crowded conditions (licences in [12_DATASET](12_DATASET_AND_DATA_COLLECTION.md)).

---

## 3. Crowd flow and spatiotemporal forecasting

### 3.1 ST-ResNet [19] — [K]

| Field | Content |
|---|---|
| Title | Deep Spatio-Temporal Residual Networks for Citywide Crowd Flows Prediction |
| Authors | J. Zhang, Y. Zheng, D. Qi |
| Year / Venue | 2017 / AAAI |
| Problem | Predict inflow/outflow of every grid cell of a city |
| Methodology | Residual CNNs over closeness, period and trend inputs, fused with external factors (weather, holidays) |
| Dataset | TaxiBJ (taxi GPS), BikeNYC (bike trips) |
| Results | Lower RMSE than ARIMA, VAR and earlier deep baselines (see paper) |
| Limitations | Regular grid assumption; citywide scale; external factors limited to weather/holiday |
| Relevance | Defines **inflow/outflow per region** as the forecasting state — the same quantities as CROWDCAST's $F^{in}_i, F^{out}_i$ — and shows the value of external covariates |

### 3.2 DCRNN [20] — [K]

| Field | Content |
|---|---|
| Title | Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting |
| Authors | Y. Li, R. Yu, C. Shahabi, Y. Liu |
| Year / Venue | 2018 / ICLR |
| Problem | Traffic speed forecasting on road sensor networks |
| Methodology | Diffusion convolution on a directed graph inside a seq2seq GRU |
| Dataset | METR-LA (207 sensors), PEMS-BAY (325 sensors) |
| Results | Improved over ARIMA, VAR, SVR, FC-LSTM at 15/30/60-min horizons (see paper) |
| Limitations | Requires months of dense sensor data; heavy training |
| Relevance | Canonical example that **directed graph diffusion** helps — but in a regime with hundreds of nodes and months of data, unlike ours |

### 3.3 STGCN [21] and Graph WaveNet [22] — [K]

| Field | STGCN [21] | Graph WaveNet [22] |
|---|---|---|
| Authors | B. Yu, H. Yin, Z. Zhu | Z. Wu, S. Pan, G. Long, J. Jiang, C. Zhang |
| Year / Venue | 2018 / IJCAI | 2019 / IJCAI |
| Methodology | Graph convolution + gated temporal convolution, fully convolutional | Dilated causal convolutions + graph convolution with **learned adaptive adjacency** |
| Datasets | PeMSD7, BJER4 | METR-LA, PEMS-BAY |
| Limitation | Fixed graph; data-hungry | Adaptive adjacency needs ample data to learn |
| Relevance | Candidate architectures for the stretch ablation A5; both are small enough to train on a laptop GPU for ≤ 20 nodes |

### 3.4 GNN survey for traffic [23] — [V]

Jiang & Luo (Expert Systems with Applications, 2022) survey GNN models for traffic forecasting and maintain a public paper list (verified: GitHub `jwwthu/GNN4Traffic`). It documents that most GNN results come from large sensor networks with long histories. **Interpretation:** at venue scale (≈ 6–15 zones, a few hours per event) the benefit of a GNN over feature-engineered models is unproven; we treat it as a hypothesis (H5).

---

## 4. Event-aware forecasting

### 4.1 DeepUrbanEvent [24], [25] — [V]

| Field | Content |
|---|---|
| Title | DeepUrbanEvent: A System for Predicting Citywide Crowd Dynamics at Big Events [24]; extended as *Predicting Citywide Crowd Dynamics at Big Events: A Deep Learning System* [25] |
| Authors | R. Jiang, X. Song, *et al.* (nine authors, last author R. Shibasaki — verified via Semantic Scholar listing; copy full list from the paper) |
| Year / Venue | 2019 / ACM KDD (Applied Data Science track) [24]; 2021/2022 / ACM TIST [25] |
| Problem | Predict crowd density and flow during **rare big events** (e.g. disasters, festivals) when normal periodic patterns break |
| Methodology | Decomposes citywide dynamics into density and flow; uses the **most recent** observations (current hour) rather than long-period history, with a recurrent/convolutional encoder–decoder |
| Dataset | Large-scale smartphone GPS records from Japan (as described by the authors) |
| Results | Outperformed baselines during big events (see paper) |
| Limitations | Citywide grid, not venue zones; requires mobile-phone GPS data; does not use an explicit event schedule |
| Relevance | Closest prior work on **event-time crowd forecasting**. Key lesson: during events, recent dynamics dominate long-term periodicity — which supports including short lags and neighbour flows. CROWDCAST differs by operating *inside* one venue with camera-derived counts and an explicit schedule |

### 4.2 Crowd forecasting with Wi-Fi sensors and LSTM [26] — [V]

| Field | Content |
|---|---|
| Title | Crowd Forecasting Based on WiFi Sensors and LSTM Neural Networks |
| Authors | U. Singh, J.-F. Determe, F. Horlin, P. De Doncker |
| Year / Venue | 2020 / IEEE Transactions on Instrumentation and Measurement, vol. 69, no. 9 |
| Problem | Multi-step-ahead forecasting of crowd counts in public spaces |
| Methodology | Crowd counts derived from Wi-Fi probe requests; LSTM networks for multi-step forecasting compared with simpler models |
| Dataset | Authors' own Wi-Fi sensor measurements |
| Results | Reported LSTM forecasting accuracy on their data (see paper) |
| Limitations | Wi-Fi counts are indirect (device ≠ person; MAC randomisation); single-area series |
| Relevance | Demonstrates the **count-series → forecast** pipeline at venue scale and motivates LSTM as a comparison model, while reminding us to compare against simple baselines |

### 4.3 Wi-Fi/Bluetooth crowd density and flow [27], data-fusion crowd monitoring [28] — [V]

Schauer et al. [27] estimated crowd densities and pedestrian flows from Wi-Fi and Bluetooth at a large venue; Duives et al. [28] fuse Wi-Fi traces with automated counting-system data to estimate flow rates in a crowd monitoring system. **Relevance:** they show that real crowd monitoring systems fuse heterogeneous, imperfect sensors — supporting our plan to fuse direct occupancy estimates with flow-integrated estimates (conservation filter, [10 §3](10_ML_FORECASTING_METHODOLOGY.md)).

### 4.4 Uncertainty in spatiotemporal forecasting [36]–[38] — [K]/[V]

Quantile regression [36] and conformalised quantile regression [37] give distribution-free prediction intervals; Mallick et al. [38] (verified on arXiv listing) quantify uncertainty in spatiotemporal GNN traffic forecasting with deep ensembles. **Relevance:** quantile gradient boosting plus split-conformal calibration is a cheap, defensible way to give operators intervals — chosen for CROWDCAST.

---

## 5. Crowd dynamics, congestion and early warning

### 5.1 Social force model [29] — [K]

Helbing & Molnár (Physical Review E, 1995) model pedestrians as particles driven by goal-directed and repulsive "social forces". **Relevance:** the basis of many microscopic simulators (including options in JuPedSim [45]); not used directly for forecasting, but informs the synthetic data generator's assumptions.

### 5.2 Dynamics of crowd disasters [30] — [K]

| Field | Content |
|---|---|
| Title | Dynamics of Crowd Disasters: An Empirical Study |
| Authors | D. Helbing, A. Johansson, H. Z. Al-Abideen |
| Year / Venue | 2007 / Physical Review E, vol. 75, 046109 |
| Problem | What happens in a crowd before a disaster |
| Methodology | Video analysis of high-density pedestrian flows during the Hajj (2006) |
| Results | Identified transitions from laminar flow to stop-and-go waves to "crowd turbulence"; proposed "crowd pressure" (density × velocity variance) as an indicator |
| Limitations | Extremely high densities; specialised setting |
| Relevance | Justifies monitoring **velocity variance** as a secondary risk signal (future work) and shows that density alone is not the whole story |

### 5.3 Level of service and crowd science [31], [32] — [K]

Fruin's pedestrian level-of-service [31] and Still's crowd-science text [32] relate space per person to comfort and flow. CROWDCAST does **not** hard-code these values; organisers set planning capacity $C_i$ and thresholds. The literature is cited as guidance for choosing defaults.

### 5.4 Conservation laws [48] — [K]

The kinematic-wave theory of Lighthill & Whitham [48] models traffic as a conserved quantity. CROWDCAST's occupancy-conservation baseline is the discrete, zone-level analogue.

---

## 6. Synthesis

| Theme | Established (from literature) | Open for CROWDCAST (our interpretation) |
|---|---|---|
| Counting | Density maps outperform detection at high density [1]–[8] | Which density band in our footage breaks the detector |
| Tracking | Motion-only ByteTrack is strong on crowded MOT data [16] | Line-crossing accuracy on our camera angles |
| Forecasting | Graph models help on large sensor networks [20]–[23]; event periods break periodicity [24] | Whether neighbour features help at ≈ 10 zones with hours of data |
| Event awareness | External covariates help citywide [19], [24] | Whether an explicit **schedule** helps zone-level forecasts |
| Uncertainty | Quantile/conformal and ensembles are viable [36]–[38] | Interval calibration under synthetic-to-real shift |

These open questions become the research questions in [research_questions.md](../RESEARCH/research_questions.md).

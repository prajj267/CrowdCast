# 12 — Dataset and Data Collection

| Field | Value |
|---|---|
| Version | 0.4 |
| Status | Proposed; no data collected yet |

---

## 1. The key distinction

Public crowd-counting datasets consist mostly of **independent still images** annotated with head points. They are suitable for evaluating *counting* (problem 1 in [01 §5](01_PROBLEM_STATEMENT.md)). They do **not** provide:

- continuous temporal sequences spanning an event (hours),
- zone partitions of a venue and their connectivity,
- inflow/outflow across zone boundaries,
- an event schedule.

Therefore CROWDCAST uses **two separate data strategies**:

| Purpose | Data |
|---|---|
| Evaluate CV counting/tracking | Public image/video datasets (§2) + our own annotated footage (§4) |
| Train and evaluate forecasting | Synthetic event time series from CROWDSIM (§5) + small real time series from our own recordings (§4) |

Every stored observation carries `data_origin ∈ {REAL, MANUAL, SYNTHETIC}`, and every reported result states which data it was computed on.

## 2. Public datasets

Tags: **[V]** facts confirmed on the dataset page during preparation; **[K]** from the dataset paper / reference knowledge — confirm on download. Licence terms must be re-read by the team before use; where we could not find an explicit licence we say so.

| Dataset | Source / access | Licence / terms | Size | Annotation | Intended application | Limitations for CROWDCAST |
|---|---|---|---|---|---|---|
| **ShanghaiTech** (Part A, Part B) [1] | Authors' repository github.com/desenzhou/ShanghaiTechDataset (Dropbox / Baidu links, "updated in 2024") [V] | The repository carries a **BSD 2-Clause** licence file; it does not say whether that covers the images — **treated as research-only**, cite [1] [V, checked 2026-11-21] | Part A 482 images, Part B 716 images; ≈ 330 k heads [K]. Downloaded archive (A + B together, B not separable): 174.4 MB; Part B test = 316 images + 316 GT files [V, 2026-11-21] | Head points (`.mat`) | Single-image counting | Still images; Part A internet images unlike our cameras; Part B closer (street CCTV-like) |
| **UCF-QNRF** [3] | https://www.crcv.ucf.edu/data/ucf-qnrf/ [V] | Research use per CRCV page — confirm [K] | 1,535 images, ≈ 1.25 M heads [K] | Head points | Extremely dense counting | Densities far above typical college events; images only |
| **JHU-CROWD++** [4] | http://www.crowd-counting.com [V] | **Academic and non-commercial use** [V] | 4,372 images, 1.51 M annotations [V] | Head points + approximate box sizes + image-level labels (weather, distractors) | Robust counting across conditions | Images only; non-commercial |
| **NWPU-Crowd** [5] | Project page / benchmark site | Research use — confirm [K] | 5,109 images, ≈ 2.13 M heads [K] | Points + boxes | Counting & localisation | Images only |
| **Mall** [9] | https://personal.ie.cuhk.edu.hk/~ccloy/downloads_mall_dataset.html [V] | "Intended for research purposes only … cannot be used commercially"; cite the listed publications [V, 2026-11-21] | 2,000 consecutive frames 640×480, > 60,000 labelled pedestrians, ROI mask; archive 91.8 MB [V] | Head points per frame | Localised counting in a fixed scene | Short (minutes), indoor, one camera — useful as a **temporal counting test clip** |
| **UCSD Pedestrian** [10] | SVCL, UC San Diego | Research use — confirm [K] | 2,000 frames, low resolution [K] | Counts / points | Video counting | Sparse, low-res walkway |
| **FDST** [11] | Released with paper (GitHub) | Confirm on repository [K] | 100 videos, 13 scenes, 15,000 frames [K] | Head points per frame | Video crowd counting | Short clips; scenes not events |
| **MOT20** [17] | https://motchallenge.net/data/MOT20/ [V] | **CC BY-NC-SA 3.0** (stated on the page) [V, 2026-11-21] | 8 sequences (4 train with ground truth, 4 test); full archive 5.0 GB, labels archive 19.2 MB (page states 13.9 MB). Per-sequence MP4s on the site are **half resolution** (e.g. 960×540 for 1920×1080), so the original frames from the full archive are used [V] | Full-body boxes + IDs | Crowded tracking | Small number of scenes |
| **CrowdHuman** [18] | Dataset website | Non-commercial research — confirm [K] | 15,000 train / 4,370 val / 5,000 test images [K] | Full, visible and head boxes | Detection under occlusion | Images only; useful if we fine-tune a head detector (extension) |

**Usage plan:**
- **Mandatory:** Mall (temporal counting test), ShanghaiTech Part B test split (counting under CCTV-like views), MOT20 (2 sequences, tracker sanity check).
- **Optional:** JHU-CROWD++ subsets (weather/night robustness), CrowdHuman (head-detector fine-tuning if needed).
- **No public dataset is used to train forecasting models.**
- **Downloaded 2026-11-21** (WORKFLOW 7.1.1) to git-ignored `data/public/`: Mall (whole), ShanghaiTech archive (Part B test extracted), MOT20 full archive (only MOT20-01 and MOT20-03 kept, original resolution) + labels.

## 3. Pedestrian simulators (for synthetic data)

| Option | Description | Decision |
|---|---|---|
| **CROWDSIM** (our own, zone-level agent model) | Agents move between zones on the venue graph with schedule-driven choices and edge capacity limits | **Selected** for forecasting data — fast (hours of event in seconds), directly produces zone-level ground truth |
| JuPedSim [45] | Open-source microscopic pedestrian dynamics simulator with a Python interface (verified on PyPI) | Optional: validate CROWDSIM's corridor capacity behaviour on one topology; check licence on repository before use |
| Commercial simulators | Planning-grade tools | Not used (cost) |

## 4. Real data collection

### 4.1 Options

| Option | Ground truth quality | Effort | Ethics burden | Planned |
|---|---|---|---|---|
| **Staged scenario** with volunteers (30–80 people) following a scripted schedule through 3–4 zones (e.g. corridor, "stage", "food court" in a campus courtyard) | **High** — script is known; counts verifiable | Medium | Low–medium (informed consent of all participants) | **Yes — primary real dataset** |
| Recording a real campus event (festival) from elevated positions | Medium — manual annotation needed | High | Medium–high (signage, institutional approval) | Yes, if approval obtained |
| Public online videos | Low (unknown geometry, rights) | Low | Copyright and privacy issues | **No** |

### 4.2 Recording protocol

1. **Approval:** institutional ethics/approval and event organiser permission **before** recording ([19](19_SECURITY_AND_PRIVACY.md)).
2. **Notice:** visible signage at recorded areas; consent forms for staged-scenario volunteers.
3. **Cameras:** 2–4 smartphones or action cameras on tripods/balconies, ≥ 3 m height if possible, angled 30–60° downward, 1080p, 25–30 FPS, landscape, fixed (no zoom).
4. **Synchronisation:** a visible clock or clap at start of each recording; record start time to the second.
5. **Geometry:** photograph and measure ≥ 4 floor reference points per camera (for optional homography); sketch zone boundaries and measure passage widths with a tape.
6. **Schedule:** write down the real schedule (staged scenario: the script) with actual start/end times.
7. **Storage:** encrypted drive, access limited to the team; retention per [19 §6](19_SECURITY_AND_PRIVACY.md).

### 4.3 Manual annotation

| Annotation | Tool | Granularity | Target volume |
|---|---|---|---|
| Head points per frame (CV counting accuracy) | CVAT or Label Studio | 1 frame / 10 s, stratified by density | ≥ 300 frames |
| Zone occupancy count | Same, counting points inside zone polygon | 1 per minute | All recorded minutes of staged scenario; ≥ 60 min of event footage |
| Line crossings | Manual tally with clicker / video playback | Per 1-min bucket per direction | ≥ 60 min |

Quality control: 10 % of frames annotated twice by different team members; report inter-annotator count difference (MAE between annotators). Annotations exported to CSV and imported as `MANUAL` observations (FR-OBS-05).

## 5. Synthetic data — CROWDSIM

**All CROWDSIM output is labelled `SYNTHETIC` in the database, files and reports.**

### 5.1 Model

Discrete-time agent model on the venue graph $G$ with tick $\delta = 10$ s.

1. **Arrivals:** non-homogeneous Poisson process at entry zones with rate $\lambda(t)$ derived from expected attendance and an arrival curve (ramp-up before headline items).
2. **Agent state:** current zone, destination, remaining dwell time.
3. **Destination choice** when dwell ends: multinomial logit over zones $k$:
   $$
   P(k \mid i, t) \propto \exp\big(\beta_a\, a_k(t) - \beta_d\, d_{ik} - \beta_c\, u_k(t)\big)
   $$
   $a_k(t)$ = attraction from active/upcoming schedule items in $k$ (higher shortly before and during performances, meal times), $d_{ik}$ = path travel time, $u_k$ = current crowding (avoidance).
4. **Movement:** along shortest path; traversing edge $(j,i)$ takes $\tau_{ji}$; edge throughput capped at $q^{max}_{ji}\delta$ agents per tick; excess agents queue in $j$ → **spillback** produces realistic congestion propagation.
5. **Speed:** zone speed $v_i = v_{free}\max(0.1, 1 - \rho_i/\rho_{jam})$ (simple speed–density assumption; parameters configurable).
6. **Departures:** leaving probability increases toward event end and after the final item ("exit wave").
7. **Schedule perturbation** (avoids trivial leakage, see [05 §6](05_GAP_ANALYSIS.md)): actual item start = published start + $\delta_s$, $\delta_s \sim \mathcal U(-5, +10)$ min; item popularity multiplier $\sim \text{LogNormal}(0, 0.3)$; 5 % chance of an unscheduled "pop-up" attraction.

### 5.2 Outputs per minute

True $N_i$, $F_{j\to i}$, $F^{in}_i$, $F^{out}_i$, $v_i$ for all zones, plus the **published** schedule (as features) and the **actual** schedule (for analysis only, never as features).

### 5.3 Observation-noise model ("CV-like" inputs)

To mimic perception error:

$$
N^{obs}_i = \operatorname{round}\big(N_i\,(1 - m(\rho_i)) + \varepsilon\big),\quad m(\rho) = \min(0.6,\, m_0 + m_1\rho),\quad \varepsilon \sim \mathcal N(0, (\sigma_r N_i)^2)
$$

Each true crossing is detected with probability $p_{det}$; false crossings occur at rate $r_{fp}$ per line per minute. Parameters $(m_0, m_1, \sigma_r, p_{det}, r_{fp})$ are **calibrated from measured CV errors on our real footage** (week 6); until then, documented placeholder values are used and labelled as such.

Experiments are run with both **clean** and **noisy** inputs (RQ5); targets are always true $N_i$ in synthetic data.

### 5.4 Topologies and volume

| Topology | Description | Zones | Events | Use |
|---|---|---|---|---|
| V1 College festival | Graph in [11 §6](11_SPATIAL_INTELLIGENCE.md) | 8 | 60 | Train/val/test |
| V2 Concert/stadium | Radial concourse with 4 gates, 2 food areas, arena | 10 | 60 | Train/val/test |
| V3 Exhibition | Grid of 6 halls + 2 corridors + 2 gates + food | 12 | 60 | **Held-out venue test only** |

Each event 4–8 h, randomised schedule (number, timing, category of items), attendance, and behavioural parameters within documented ranges. Approximate volume: 180 events × ≈ 360 min × ≈ 10 zones ≈ 650 k zone-minutes.

### 5.5 Validity checks for synthetic data

- Venue-level conservation holds exactly (unit test).
- Plausibility review: peak occupancy profiles reviewed against the real staged scenario and organiser expectations.
- Sensitivity: results re-run with a second parameter regime to check conclusions are not artefacts of one setting.

## 6. Data formats

| Artefact | Format |
|---|---|
| Observations export | Parquet / CSV: `event_id, zone_code, bucket_start, occupancy, inflow, outflow, mean_speed_mps, quality, data_origin` |
| Event + published schedule | YAML, format version 1 — specified in §6.2 (CSV variant not implemented; YAML covers the same fields) |
| Venue | YAML, format version 1 — specified in §6.1 |
| Annotation import | CSV: `zone_code, minute (ISO 8601), count[, inflow, outflow]` |
| Training dataset | Parquet with feature columns, target columns per horizon, `event_id`, `split`, `data_origin` |

### 6.1 Venue YAML (format version 1)

Implemented and validated by `backend/crowdcast/venue_graph/config.py` (Pydantic v2). Files live in `configs/venues/`. Unknown keys are errors (typos are not silently ignored).

```yaml
format_version: 1            # required; only 1 is accepted
illustrative: true           # required; true = made-up values (design/simulation only), false = organiser-supplied
venue:
  name: North Campus Grounds # required
  address: Example University          # optional
  rho_plan: 1.5              # optional, persons/m², 0 < x < 100; organiser-entered (11 §4)
  plan_width: 1200           # optional plan size in plan units; if both set, polygons must lie inside
  plan_height: 800
  floor_plan_path: null      # optional
zones:
  - code: MS                 # ^[A-Z0-9_]{1,16}$, unique; "OUTSIDE" is reserved
    name: Main Stage
    type: STAGE              # one of the 11 zone types in 11 §2
    area_m2: 2000            # usable area A_i, > 0
    capacity: 3000           # C_i, integer > 0; omit/null -> floor(A_i * rho_plan), error if rho_plan unset
    polygon: [[600, 100], [1100, 100], [1100, 450], [600, 450]]   # 3–100 vertices, simple (Shapely is_valid), area > 0
    thresholds: {elevated: 0.6, high: 0.8, critical: 0.95}         # optional, each optional; resolved values strictly increasing
connections:
  - from: OUTSIDE            # zone code or OUTSIDE (the virtual node ω, stored as NULL zone_id)
    to: G1
    width_m: 8               # boundary width w_ji, > 0
    travel_time_s: 20        # typical travel time τ_ji, integer > 0
    bidirectional: true      # default true; false = one-way passage (e.g. exit-only gate)
```

Rules checked when the file is loaded:

| Rule | Error when |
|---|---|
| Codes | duplicate code; code `OUTSIDE`; pattern mismatch |
| References | a connection names an unknown zone; `from == to` (includes OUTSIDE→OUTSIDE) |
| Duplicate edges | the same directed edge appears twice, counting both directions of bidirectional connections |
| Capacity | `capacity` missing and venue `rho_plan` not set |
| Geometry | polygon invalid or outside the plan bounds |
| Limits | values mirror the DB columns in [13](13_DATABASE_DESIGN.md) |

**Entry/exit flags are derived, not written:** a zone is an entry if a directed edge OUTSIDE→zone exists, and an exit if zone→OUTSIDE exists; these fill `zones.is_entry` / `is_exit`. Whole-graph rules (degree, reachability from and to ω, 11 §9) are checked by the graph module, not by the file parser.

### 6.2 Event and published-schedule YAML (format version 1)

Implemented and validated by `backend/crowdcast/venue_graph/event_config.py`. Files live in `configs/events/`; one file = one event at one venue. The schedule in this file is the **published** schedule — the only schedule that may be used as forecasting features. Realised times (CROWDSIM perturbations, operator corrections) are analysis-only ([10 §7](10_ML_FORECASTING_METHODOLOGY.md), §5.1 step 7).

```yaml
format_version: 1                  # required; only 1 is accepted
illustrative: true                 # required; true = made-up event
event:
  name: Spring Fest 2027 - Day 1
  venue: v1                        # stem of a file in configs/venues/
  start_time: 2027-03-12T10:30:00Z # ISO 8601 WITH time zone; converted to UTC; naive times rejected
  end_time: 2027-03-12T17:30:00Z   # after start_time; duration ≤ 24 h (14 §3.2)
  expected_attendance: 5000        # optional, ≥ 0
  is_synthetic: true               # default false
schedule:
  - title: Headline band
    category: PERFORMANCE          # PERFORMANCE | MEAL | ENTRY_OPEN | EXIT_WAVE | ANNOUNCEMENT | OTHER
    zone: MS                       # zone code of the event's venue; omit/null = venue-wide
    start: 2027-03-12T14:00:00Z    # with time zone; end after start; inside the event window
    end: 2027-03-12T15:00:00Z
    expected_attendance: 2500      # optional, ≥ 0
    attraction_weight: 0.95        # 0–1, at most 2 decimals (DB numeric(3,2)); default 0.5
```

Errors: unknown keys; naive times; event or item ending before it starts; event longer than 24 h; item outside the event window; attendance < 0; weight outside 0–1 or with more than 2 decimals; a `zone` not present in the venue file (checked when the event is matched to its venue).

### 6.3 Camera YAML (format version 1)

Implemented by `backend/crowdcast/venue_graph/camera_config.py`; files in `configs/cameras/`. One file per camera. Pixel coordinates refer to the video's own frame size. The video itself is never committed (git-ignored `videos/`).

```yaml
format_version: 1
camera:
  code: CAM1                       # ^[A-Z0-9_]{1,16}$
  venue: v1                        # stem of a file in configs/venues/
  source: videos/public/clip.mp4   # path relative to the repo root
  recording_start: 2026-11-01T10:00:00Z   # EVENT time of frame 0 (frame i = start + i / fps)
  sample_fps: 5                    # 0 < x <= 30; doc 09 §3 default 5
  image_width: 1920
  image_height: 1080
  detector: yolox_s                # yolox_nano | yolox_tiny | yolox_s (default yolox_s)
  tiled: true                      # tiled detection for small people (WORKFLOW 1.4.3)
regions:                           # zone areas visible in this camera
  - zone: C1                       # zone code of the venue
    polygon_px: [[0, 0], [900, 0], [900, 1000], [0, 1000]]   # simple polygon inside the image
    coverage_fraction: 1.0         # κ in (0, 1]: visible share of the zone's usable area (09 §6.1)
    primary: true                  # at most one primary region per zone (09 §8)
lines:                             # counting lines (09 §6.2)
  - from: C1                       # a connection of the venue graph (either orientation; OUTSIDE allowed)
    to: MS
    p1: [950, 0]
    p2: [950, 1080]
    positive_side: MS              # crossing towards this side = entering this zone
```

Errors: unknown keys; naive `recording_start`; self-intersecting polygons; points outside the image; two primary regions for one zone; a line whose `positive_side` is not one of its ends; and (when checked against the venue) unknown zones or a line on a connection the venue does not have.

## 7. Data labelling summary

| Label | Meaning | Allowed uses |
|---|---|---|
| `REAL` | CV pipeline on real recorded footage | Evaluation; demo; test-only forecasting |
| `MANUAL` | Human-annotated counts | Ground truth for CV and real forecasting evaluation |
| `SYNTHETIC` | CROWDSIM output (clean or noisy, distinguished by `method = SIM_CLEAN / SIM_NOISY`) | Training; ablations; demo (labelled in UI) |

## 8. Change log

| Version | Date | Change |
|---|---|---|
| 0.4 | 2026-11-21 | §6.3 added: camera YAML format v1 (event-time start, regions with coverage and primary flag, counting lines on venue connections) — WORKFLOW 6.1.2 |
| 0.3 | 2026-11-20 | §6.2 added: event + published-schedule YAML format v1 (UTC conversion, event-window and venue-zone checks) — WORKFLOW 2.1.3 |
| 0.2 | 2026-11-20 | §6.1 added: full venue YAML format v1 (`format_version`, `illustrative` flag, field limits, derived entry/exit flags, load-time rules) — WORKFLOW 2.1.1 |

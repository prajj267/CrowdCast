# 04 — Existing Systems Analysis

| Field | Value |
|---|---|
| Version | 0.1 |
| Evidence date | Vendor pages consulted November 2026 |

---

## 0. Evidence rules

1. Claims about commercial products come **only** from the vendor's own public pages or reputable trade press, cited as [W#] in [bibliography.md](../RESEARCH/bibliography.md).
2. Public marketing pages describe what a vendor chooses to advertise. **If a page does not mention a feature, we record "not advertised on the pages reviewed" — never "absent".** Vendors may offer unadvertised or custom capabilities.
3. Accuracy figures quoted by vendors are vendor claims, not independently verified.

---

## 1. Commercial systems

### 1.1 CrowdVision (now part of iinside) [W1], [W2]

| Aspect | Evidence-based description |
|---|---|
| Primary functionality | Automated passenger analytics for airports: passenger flows, queue lengths, wait times, processing periods, asset utilisation; real-time dashboards and occupancy-level alerts; historical data for planning [W1] |
| Technology | Processes live video from commercial off-the-shelf overhead cameras with fisheye lenses; AI distinguishes people from objects such as bags; measures speed and direction; combines views from multiple cameras [W1] |
| Privacy approach | Downward-looking sensors produce "anonymous, non-personal data"; by default video is not retained after analysis [W1] |
| Prediction capability | Forecasting of future flows is **not advertised on the page reviewed** [W1]. Unknown beyond that |
| Target applications | Airports (security checkpoints, retail, passenger journey) |
| Corporate status | Merged with iinside in 2020 [W2] |
| Vendor accuracy claim | "more than 95% accurate" (vendor claim, metric undefined) [W1] |
| Differences from CROWDCAST | Mature, multi-camera commercial product for continuous airport operations. CROWDCAST targets temporary event venues, short-horizon zone forecasting tied to an event schedule, and is an open academic prototype |

### 1.2 WaitTime [W3]

| Aspect | Evidence-based description |
|---|---|
| Primary functionality | "Real-time data and historical analytics on crowd behavior"; modules for entry/exit counting at high volume, unstructured and structured queues, and "massing" (density % measurement); real-time operations dashboard; custom real-time crowd alerts; guest-facing wait-time displays (green/yellow/red bars) via IPTV and mobile app; open API [W3] |
| Technology | Patented AI on camera feeds; licensing tiered by number of cameras [W3] |
| Prediction capability | The products page describes real-time and historical analytics; **forecasting is not advertised on the page reviewed** [W3] |
| Target applications | Stadiums, arenas, convention centres and other entertainment venues |
| Differences from CROWDCAST | WaitTime focuses on real-time measurement and guest communication at production scale. CROWDCAST explores *forecasting* of zone occupancy and its propagation through a venue graph, with evaluation of warning lead time |

### 1.3 Density (density.io) [W4]

| Aspect | Evidence-based description |
|---|---|
| Primary functionality | Occupancy sensing for workplaces; real-time and historical occupancy data [W4] |
| Technology | Anonymous radar sensor ("Waffle") reporting 0, 1, 2 or 3+ people per sensor area [W4] |
| Prediction capability | Not advertised on the pages reviewed |
| Target applications | Offices / workplace space utilisation |
| Differences from CROWDCAST | Designed for low-occupancy indoor spaces, not dense outdoor events. Relevant as a **privacy-by-design** reference: non-camera sensing that cannot identify people |

### 1.4 "DensityAI" (named in the project brief)

A search for a crowd-analytics product named **DensityAI** found no such product. Results referred to an unrelated AI-hardware start-up and to a mammographic breast-density algorithm ("densityAI" by Densitas). **We therefore exclude it** rather than describe a product we cannot verify. If the team has a specific vendor in mind, add its URL and re-assess.

### 1.5 Other categories (described generically, not product-specific)

| Category | Typical capability | Why relevant | Evidence status |
|---|---|---|---|
| Video-analytics modules in VMS/CCTV suites | Line crossing, area occupancy, crowd-detected alarms | Shows that counting and thresholds are commodity features | General industry knowledge — no product claims made |
| Pedestrian simulation software for venue planning | Offline what-if simulation of evacuation and circulation | Used **before** events; complementary to live forecasting | General knowledge; open example: JuPedSim [45] |
| Wi-Fi/Bluetooth crowd monitoring | Device-count-based density and flows [27], [28] | Non-visual alternative; indirect counts | Academic sources |

---

## 2. Academic and open-source systems

| System | Type | Functionality | Prediction | Limitations | Relation to CROWDCAST |
|---|---|---|---|---|---|
| DeepUrbanEvent [24], [25] | Research system (KDD ADS) | Citywide crowd density/flow during big events from GPS | Yes — short-term, citywide grid | Needs phone GPS data; city scale | Closest forecasting precedent; different scale and sensing |
| Wi-Fi + LSTM forecasting [26] | Research system | Crowd counts from Wi-Fi probes; LSTM multi-step forecasts | Yes — single area | Indirect counts; no spatial coupling | Precedent for count-series forecasting |
| Crowd monitoring data fusion [28] | Research system | Fuses Wi-Fi traces and counting systems to estimate flows | Estimation, not forecasting | Sensor-specific | Supports sensor fusion design |
| Ultralytics solutions [13] | Open-source library (AGPL-3.0) | Object counting in regions, line crossing, heatmaps on top of YOLO + trackers | No | General-purpose; not venue-aware | Building block for our CV module |
| `supervision` (Roboflow) | Open-source library (MIT) | ByteTrack wrapper, `LineZone`, `PolygonZone`, annotators | No | General-purpose | Building block; MIT licence eases reuse |
| JuPedSim [45] | Open-source simulator | Microscopic pedestrian dynamics, Python API | Simulation, not forecasting | Requires scenario setup | Optional source of synthetic validation data |

---

## 3. Comparison matrix

Legend: ✔ advertised/reported; — not advertised on reviewed pages (absence **not** implied); n/a not applicable.

| Capability | CrowdVision | WaitTime | Density | DeepUrbanEvent | CROWDCAST (proposed) |
|---|---|---|---|---|---|
| Real-time people counting | ✔ | ✔ | ✔ | n/a (GPS) | ✔ (planned) |
| Flow / direction | ✔ | ✔ (entry/exit) | — | ✔ | ✔ (planned, line crossing) |
| Queue / wait time | ✔ | ✔ | — | n/a | — (out of scope) |
| Density / occupancy % | ✔ (alerts) | ✔ ("massing") | ✔ | ✔ | ✔ (planned) |
| Historical analytics | ✔ | ✔ | ✔ | n/a | ✔ (planned) |
| Short-term forecasting | — | — | — | ✔ | ✔ (planned, research focus) |
| Event-schedule input | — | — | — | — (not used, per paper) | ✔ (planned) |
| Venue-graph propagation | — | — | — | grid-based | ✔ (planned, feature-based) |
| Prediction intervals | — | — | — | — | ✔ (planned) |
| Production maturity | High | High | High | Research | Student prototype |

**Reading the matrix correctly:** CROWDCAST's planned features overlap substantially with mature products for *measurement*. Its distinguishing focus is the **forecasting experiment** (schedule + neighbour features, evaluated by lead time), not superior counting. CROWDCAST is not expected to outperform commercial systems on measurement accuracy.

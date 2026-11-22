# CROWDCAST — Event Crowd Congestion Prediction

CROWDCAST estimates how many people are in each zone of an event venue from video, forecasts each
zone's occupancy **5, 15 and 30 minutes ahead** with uncertainty intervals, and warns operators
about zones likely to become congested before the congestion forms.

It is a college CSE project with a research component, built by a single developer on one
CPU-only laptop (no GPU).

> **Status: experiments in progress (Phase 7).** The full pipeline is built and tested: CPU
> computer vision on public clips, synthetic event generation (CROWDSIM), ingestion API,
> baselines, XGBoost quantile forecasts with conformal intervals, the alert engine and a
> five-page React dashboard. Final forecasting results are **not yet available**; every run done
> so far, with its data origin, is in [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md). Progress is tracked
> in [WORKFLOW.md](WORKFLOW.md).

## Research question

> Do event-schedule and neighbouring-zone features improve short-horizon congestion forecasts and
> warning lead time, compared with independent zone-wise models?

Either answer is a valid result. Hypotheses and experimental design:
[RESEARCH/](RESEARCH/research_questions.md).

## How it works

```
recorded video ──► person detection (YOLOX, CPU) ──► tracking (ByteTrack) ──► per-zone counts
                                                                          and boundary flows
CROWDSIM (synthetic events) ─────────────────────────────────────────────┐        │
                                                                         ▼        ▼
             POST /api/crowd/observations  (one ingestion contract)  ──► PostgreSQL
                                                                         │
             baselines + XGBoost quantile forecasts (5/15/30 min) ◄──────┘
                                  │
                     risk levels and alerts ──► React dashboard
```

- **Computer vision** runs offline on recorded public clips; only aggregate counts are kept.
- **Forecasting** is evaluated on synthetic events (CROWDSIM), because no real multi-zone event
  dataset is available. Forecasting conclusions are therefore synthetic evidence and are reported
  as such.
- **Baselines first:** every learned model is compared with persistence, moving-average,
  linear-trend and conservation baselines at every horizon.

## What is built

| Area | Where |
|---|---|
| PostgreSQL 16 schema (13 tables with constraints), Alembic migration | `backend/crowdcast/storage/` |
| Venue graph from YAML (zones, connections, validation) | `backend/crowdcast/venue_graph/`, `configs/venues/` |
| Ingestion API: one contract for every source (`POST /api/crowd/observations`) | `backend/crowdcast/ingestion/`, `backend/crowdcast/api/` |
| Computer vision on CPU: YOLOX via ONNX Runtime with tiling, ByteTrack, zone counts and line crossings per minute | `backend/crowdcast/vision/`, `backend/crowdcast/aggregation/` |
| CV evaluation on public data (Mall, ShanghaiTech B, MOT20) | `backend/tools/vision/` |
| CROWDSIM synthetic events (three venue topologies) with a noise model calibrated on the CV errors | `backend/tools/crowdsim/` |
| Baselines B0–B3, one shared `FeatureBuilder`, XGBoost quantile models, split-conformal intervals | `backend/crowdcast/forecasting/` |
| Prediction cycle in event time, congestion levels, alert state machine with hysteresis | `backend/crowdcast/forecasting/cycle.py`, `backend/crowdcast/risk/` |
| Training, tuning, ablation, statistics and operational evaluation tools | `backend/tools/training/` |
| React dashboard: Live, Predictions, Alerts, History, Event & venue | `frontend/` |
| End-to-end smoke test, prediction-cycle timing check, privacy check, CI | `backend/tools/`, `scripts/`, `.github/workflows/` |

Not built (solo scope, see [WORKFLOW.md](WORKFLOW.md)): authentication, editing configuration
in the browser, live camera streams, manual-annotation import, LSTM and GNN models.

## Quick start (Windows, PowerShell)

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker Desktop, Node.js 24, Git.

```powershell
git clone https://github.com/prajj267/CrowdCast.git
cd CrowdCast
copy .env.example .env                      # development settings
docker compose up -d db                     # PostgreSQL 16 on 127.0.0.1:5432
cd backend
uv sync                                     # installs Python 3.12 + dependencies
uv run alembic upgrade head                 # create the schema
uv run pytest                               # all tests (db tests skip if Postgres is down)
```

All checks at once (from the repo root): `powershell -ExecutionPolicy Bypass -File scripts\check.ps1`.
The same checks run on GitHub Actions for every push.

### Run a synthetic event end to end

Each long-running command needs its own terminal; run them from `backend/` unless stated otherwise.

```powershell
uv run python -m tools.load_config venue ../configs/venues/v1.yaml
uv run python -m tools.load_config event ../configs/events/v1_spring_fest_day1.yaml   # prints event_id
uv run python -m tools.crowdsim.run --event ../configs/events/v1_spring_fest_day1.yaml # prints the run folder
uv run uvicorn crowdcast.api.app:app                                                  # API on :8000
uv run python -m tools.crowdsim.replay <run folder> --event-id <event_id> --speedup 60
uv run python -m tools.run_predictions --event-id <event_id> --follow
cd ../frontend; npm install; npm run dev                                              # http://127.0.0.1:5173
```

Without an active model, every forecast is the persistence fallback and is labelled as such.
Training commands are listed in [CLAUDE.md §10](CLAUDE.md); model files are written to the
git-ignored `models/` folder and are not distributed.

### Computer vision (optional)

Downloads about 60 MB of YOLOX weights into `models/` (git-ignored):

```powershell
uv run python -m tools.vision.fetch_models  # download + verify SHA-256
uv run python -m tools.vision.run_camera --camera ../configs/cameras/shibuya_cam1.yaml --event-id <id> --dry-run
```

The camera YAML names a public clip that must be downloaded into `videos/public/` first (see
*Third-party material*).

## Repository layout

```
├── backend/            Python package `crowdcast` (one folder per module), tools/ (CLIs), tests/
├── frontend/           React dashboard (React 18, TypeScript, Vite)
├── configs/            venue/event/camera YAML, CROWDSIM regimes and noise, splits.json (frozen), tuned parameters
├── DOCUMENTATION/      21 specifications — source of truth for contracts and methods (INDEX.md)
├── RESEARCH/           research questions, hypotheses H1–H7, experimental design, bibliography
├── ARCHITECTURE/       Mermaid diagrams
├── PROJECT_MANAGEMENT/ original team plan (superseded on scope by WORKFLOW.md)
├── learning/           plain-language concept notes (viva preparation)
├── WORKFLOW.md         progress tracker, decisions, deviation log, session log
├── EXPERIMENT_LOG.md   every benchmark / training / evaluation run
└── CLAUDE.md           working instructions for the AI coding assistant used on this project
```

The documents in `DOCUMENTATION/` and `PROJECT_MANAGEMENT/` were written for a 4-person team with
a GPU; [WORKFLOW.md](WORKFLOW.md) records the reduced solo scope and every deviation from them.

## Technology

| Layer | Technology |
|---|---|
| Vision | YOLOX (Apache-2.0) via ONNX Runtime on CPU, OpenCV, Shapely; ByteTrack implemented in-house |
| Forecasting | pandas, NumPy, XGBoost (quantile regression), scikit-learn, Optuna, SciPy, NetworkX |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3 |
| Database | PostgreSQL 16 (Docker) |
| Frontend | React 18, TypeScript, Vite, TanStack Query, React Router, Recharts, Tailwind CSS, Vitest |

## Data, privacy and ethics

- Aggregate counts only: no facial recognition, re-identification, stored frames, crops or tracks.
- No own recordings of people; only public datasets and openly licensed clips are used.
- Videos, datasets and model weights are **never committed** (`data/`, `videos/`, `models/`,
  `runs/` are git-ignored).
- Every observation carries its origin (`REAL`, `MANUAL` or `SYNTHETIC`); results from different
  origins are never mixed.
- CROWDCAST is decision support, **not** a safety-certified system.

## Third-party material

- YOLOX ONNX models: [Megvii-BaseDetection/YOLOX](https://github.com/Megvii-BaseDetection/YOLOX),
  release 0.1.1rc0, Apache-2.0. Not redistributed here; fetched by `tools/vision/fetch_models.py`.
- Benchmark clip (not redistributed): "Shibuya Crossing, Tokyo, Japan (video).webm" by Basile
  Morin, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Shibuya_Crossing,_Tokyo,_Japan_(video).webm),
  CC BY-SA 4.0.
- Public datasets used for CV evaluation (not redistributed): Mall, ShanghaiTech Part B and MOT20.
  Their sources and licence status are recorded in
  [DOCUMENTATION/12 §2](DOCUMENTATION/12_DATASET_AND_DATA_COLLECTION.md).

## Licence

No licence has been chosen yet, so all rights are reserved by default.

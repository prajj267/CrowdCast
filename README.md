# CROWDCAST — Event Crowd Congestion Prediction

CROWDCAST estimates how many people are in each zone of an event venue from video, forecasts each
zone's occupancy **5, 15 and 30 minutes ahead** with uncertainty intervals, and warns operators
about zones likely to become congested before the congestion forms.

It is a college CSE project with a research component, built by a single developer on one
CPU-only laptop (no GPU).

> **Status: Phase 1 (foundations) in progress.** The database, tooling and a CPU person detector
> are built and tested. **No forecasting results exist yet.** Every run that has been done is in
> [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md).
> Progress is tracked in [WORKFLOW.md](WORKFLOW.md).

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

## What is built so far

| Area | State |
|---|---|
| Python environment (uv, Python 3.12), ruff, mypy (strict), pytest, pre-commit | Done |
| PostgreSQL 16 schema (13 tables, constraints that reject invalid data), Alembic migration | Done |
| YOLOX ONNX person detector on CPU (letterbox → decode → NMS), checksummed model fetch | Done |
| CPU speed benchmark of YOLOX nano/tiny/s | Done (see EXPERIMENT_LOG.md) |
| Tiled detection for small, distant people (provisional default: YOLOX-s + tiles) | Done; accuracy not yet measured |
| Venue graph, CROWDSIM, ingestion API, baselines, XGBoost, dashboard | Not started |

## Quick start (Windows, PowerShell)

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker Desktop, Git.

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

Detector (optional, downloads ≈ 60 MB of YOLOX weights into `models/`, which is git-ignored):

```powershell
uv run python -m tools.vision.fetch_models  # download + verify SHA-256
uv run python -m tools.vision.bench_detector --video <path-to-a-public-clip>
```

All checks at once (from the repo root): `powershell -ExecutionPolicy Bypass -File scripts\check.ps1`.

## Repository layout

```
├── backend/            Python package `crowdcast` (storage, vision, …), tools/, tests/
├── frontend/           React dashboard (not started)
├── configs/            venue/event/camera YAML; vision/yolox_models.yaml (model sources + checksums)
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
| Vision | YOLOX (Apache-2.0) via ONNX Runtime on CPU, OpenCV, ByteTrack (planned) |
| Forecasting | pandas, XGBoost (quantile regression), scikit-learn, Optuna (planned) |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3 |
| Database | PostgreSQL 16 (Docker) |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Recharts, Tailwind CSS (planned) |

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

## Licence

No licence has been chosen yet, so all rights are reserved by default.

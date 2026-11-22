# 18 — Deployment Plan

| Field | Value |
|---|---|
| Version | 0.2 (solo scope; replaces the v0.1 container plan, see §8) |
| Target | One Windows 11 laptop (CPU only): PostgreSQL in Docker, everything else runs natively |
| Diagram | [ARCHITECTURE/deployment_architecture.mmd](../ARCHITECTURE/deployment_architecture.mmd) |

---

## 1. Environments

| Environment | Purpose | Data |
|---|---|---|
| `dev` | The developer laptop; hot reload (uvicorn `--reload`, Vite) | Synthetic events, public clips, test fixtures |
| `demo` | The same laptop, started from a fresh clone (§5) | SYNTHETIC replay of a V1 event for forecasting and alerts; REAL observations from a public clip for the CV part (decision D4) |
| `ci` | GitHub Actions (`.github/workflows/ci.yml`) | PostgreSQL 16 service container; no videos, datasets or model weights |

No paid cloud service, no GPU and no reverse proxy are used. Everything listens on `127.0.0.1` only.

## 2. Processes

```mermaid
flowchart TB
  subgraph Laptop[Windows laptop]
    DB[(PostgreSQL 16<br/>Docker container crowdcast-db<br/>volume crowdcast-pgdata)]
    API[API<br/>uvicorn crowdcast.api.app:app<br/>:8000]
    CYC[Cycle driver<br/>tools.run_predictions --follow<br/>M6 + M7]
    SRC[Observation source<br/>tools.crowdsim.replay or<br/>tools.vision.run_camera]
    FE[Dashboard<br/>Vite dev server :5173<br/>proxies /api to :8000]
    API --> DB
    CYC --> DB
    SRC -- POST /api/crowd/observations --> API
  end
  Browser[Browser on the same laptop] --> FE
  FE --> API
```

| Process | Command (from `backend/` unless stated) | Notes |
|---|---|---|
| PostgreSQL | `docker compose up -d db` (repo root) | Only container. Port bound to `127.0.0.1`. Credentials from `.env` |
| API | `uv run uvicorn crowdcast.api.app:app` | One process. Migrations are **not** run on start; run `uv run alembic upgrade head` first |
| Cycle driver | `uv run python -m tools.run_predictions --event-id N --follow` | Replaces the documented scheduler: one cycle per newly completed minute bucket, in event time ([10 §12](10_ML_FORECASTING_METHODOLOGY.md)). Loads the active model before the first cycle |
| Observation source | `uv run python -m tools.crowdsim.replay <run dir> --event-id N` or `uv run python -u -m tools.vision.run_camera --camera <yaml> --event-id N` | Both use the single ingestion contract (AD-02). CV runs offline on recorded clips on the CPU |
| Dashboard | `npm run dev` (in `frontend/`) | Development server; `npm run build` produces a static build, which is not deployed separately |

## 3. Configuration

`.env` at the repository root (never committed; copy `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | `crowdcast` / `change-me` / `crowdcast` / `5432` | PostgreSQL container |
| `DATABASE_URL` | `postgresql+psycopg://crowdcast:change-me@127.0.0.1:5432/crowdcast` | Backend connection. Use `127.0.0.1`, not `localhost` (IPv6 stall on this machine) |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed dashboard origin |
| `RETENTION_DAYS_DATA` | `365` | Recorded setting; no deletion job exists (WORKFLOW Deviation log, 2026-11-22) |

Not used (D7 no authentication, 9.4 audit): `JWT_SECRET`, `FERNET_KEY`, `CV_API_KEY`, `PREDICTION_OFFSET_S`, `MODEL_DIR`, `RETENTION_DAYS_VIDEO`. Model artefacts are always read from `<repo>/models/`.

## 4. Hardware and disk

| Item | Development and demo machine |
|---|---|
| CPU / RAM | Ryzen 7 8840HS (8 cores), 31 GB RAM |
| GPU | None used (AMD iGPU, no CUDA). CV runs on the CPU, offline |
| Software | Windows 11, Docker Desktop (WSL2), uv (manages Python 3.12), Node.js 24, Git |
| Disk | Git-ignored folders: `models/` (YOLOX weights about 60 MB plus trained boosters), `data/` (synthetic dataset and public datasets), `videos/`, `runs/`. Check free space before generating datasets or downloading public data |

## 5. Deployment procedure (demo, from a fresh clone)

1. `git clone https://github.com/prajj267/CrowdCast.git`, then `cd CrowdCast` and `copy .env.example .env`.
2. Start Docker Desktop, then run `docker compose up -d db`.
3. In `backend/`: `uv sync`, then `uv run alembic upgrade head`.
4. Load the demo venue and event: `uv run python -m tools.load_config venue ../configs/venues/v1.yaml`, then `uv run python -m tools.load_config event ../configs/events/v1_spring_fest_day1.yaml`. Note the printed `event_id`.
5. Model (optional). A fresh clone contains **no trained model** (weights are never committed). Either run without one: every forecast is then the B0 persistence fallback, labelled as such on the dashboard. Or rebuild it from committed code: `uv run python -m tools.crowdsim.generate` (SYNTHETIC dataset), then `uv run python -u -m tools.training.train --feature-set A4` (on a clean working tree), then activate the new row with `POST /api/models/{id}/activate`.
6. Simulate the event: `uv run python -m tools.crowdsim.run --event ../configs/events/v1_spring_fest_day1.yaml`.
7. Start the API (`uv run uvicorn crowdcast.api.app:app`), the cycle driver (`uv run python -m tools.run_predictions --event-id N --follow`) and the dashboard (`npm install` once, then `npm run dev` in `frontend/`), each in its own terminal.
8. Replay the observations: `uv run python -m tools.crowdsim.replay <run dir> --event-id N --speedup 60`.
9. Check: `GET http://127.0.0.1:8000/api/health` returns `status: "ok"`, and `last_prediction_cycle` advances while the replay runs. Open http://127.0.0.1:5173.
10. CV part (optional): `uv run python -m tools.vision.fetch_models` (about 60 MB, checksums verified). Download the public clip named in `configs/cameras/shibuya_cam1.yaml` into `videos/public/`. Load `configs/venues/shibuya_demo.yaml` and `configs/events/shibuya_clip_demo.yaml`, then run `tools.vision.run_camera` with that `event_id` (the event must be `LIVE`; `--dry-run` posts nothing).

The same chain, minus the dashboard, is automated on a throwaway database by `uv run python -m tools.smoke_e2e` (WORKFLOW 9.1).

## 6. Operations

| Concern | Approach |
|---|---|
| Logs | Plain-text logs to the console of each process; every API response carries `X-Request-ID` |
| Health | `GET /api/health`: database reachability and the time of the last prediction cycle (`503` if the DB is down) |
| Backups | None scheduled. Every database row can be regenerated from committed configuration, seeds and code (CROWDSIM, replay, cycle). Experiment outputs live in `runs/` and are logged in `EXPERIMENT_LOG.md` |
| Upgrades | Alembic migrations |
| Demo resilience | The demo uses recorded or simulated data only; a replay can be re-run at any speed with identical results (event time, idempotent upserts) |

## 7. Future options (out of scope)

Containers for the API, cycle driver and frontend; a scheduler service; live RTSP cameras; edge inference next to cameras sending only counts; TimescaleDB; authentication (D7).

## 8. Change log

| Version | Date | Change |
|---|---|---|
| 0.2 | 2026-11-23 | Rewritten for the solo scope (9.4 audit, F-18): one laptop, Postgres-only Docker Compose, native processes, CLI cycle driver instead of an APScheduler container, CPU-only offline CV instead of a GPU worker, no caddy/TLS, no auth secrets; fresh-clone procedure matches the commands that exist |
| 0.1 | — | Team plan: Docker Compose with postgres, api, scheduler, cv-worker (GPU), frontend (nginx) and caddy |

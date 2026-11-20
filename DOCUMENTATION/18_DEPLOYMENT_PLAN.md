# 18 — Deployment Plan

| Field | Value |
|---|---|
| Version | 0.1 |
| Target | Single machine (team laptop/desktop or lab PC), Docker Compose |
| Diagram | [ARCHITECTURE/deployment_architecture.mmd](../ARCHITECTURE/deployment_architecture.mmd) |

---

## 1. Environments

| Environment | Purpose | Data |
|---|---|---|
| `dev` | Developer machines; hot reload | Synthetic fixtures |
| `demo` | Lab PC with GPU for milestone demos and final presentation | Synthetic events + replayed recorded footage |
| `ci` | GitHub Actions | Ephemeral PostgreSQL container |

No paid cloud service is required. Local deployment keeps footage on controlled hardware and avoids GPU cloud costs.

## 2. Containers

```mermaid
flowchart TB
  subgraph Host[Demo machine - Docker Compose]
    RP[caddy<br/>reverse proxy, TLS] --> FE[frontend<br/>nginx static build]
    RP --> API[api<br/>uvicorn FastAPI]
    SCH[scheduler<br/>APScheduler: M6 + M7]
    CV[cv-worker<br/>M1-M3, GPU]
    DB[(postgres:16<br/>volume pgdata)]
    API --> DB
    SCH --> DB
    CV -- HTTP + API key --> API
    VOL1[[volume: videos, read-only]] --> CV
    VOL2[[volume: models]] --> SCH
    VOL2 --> API
  end
  Browser[Operator browser] -- HTTPS --> RP
```

| Service | Image | Notes |
|---|---|---|
| `postgres` | `postgres:16` | Named volume `pgdata`; not exposed outside the Docker network |
| `api` | `crowdcast-backend` | `uvicorn crowdcast.api.main:app --workers 2`; runs Alembic migrations on start |
| `scheduler` | `crowdcast-backend` | `python -m crowdcast.forecasting.scheduler`; exactly one replica |
| `cv-worker` | `crowdcast-cv` (backend + PyTorch/CUDA) | NVIDIA GPU reservation; CPU profile available |
| `frontend` | `crowdcast-frontend` | Multi-stage build → nginx static |
| `caddy` | `caddy:2` | TLS with local CA for demo; plain HTTP only on localhost |

Profiles: `--profile gpu` starts the CV worker; `--profile sim` starts a CROWDSIM replay container instead (demo without footage).

## 3. Configuration

`.env` (never committed; `.env.example` committed):

| Variable | Example | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://crowdcast:***@postgres:5432/crowdcast` | DB connection |
| `JWT_SECRET` | 64 random bytes | Token signing |
| `FERNET_KEY` | generated | Encrypt camera URIs |
| `CORS_ORIGINS` | `https://localhost` | Allowed frontend origin |
| `PREDICTION_OFFSET_S` | `10` | Cycle offset after minute boundary |
| `MODEL_DIR` | `/models` | Model registry path |
| `CV_API_KEY` | per worker | SERVICE authentication |
| `RETENTION_DAYS_DATA` / `RETENTION_DAYS_VIDEO` | `365` / `30` | Retention jobs |

## 4. Hardware

| Role | Minimum | Recommended |
|---|---|---|
| Demo machine | 4-core CPU, 16 GB RAM, no GPU (CV processed offline) | 6–8-core CPU, 16–32 GB RAM, NVIDIA GPU ≥ 6 GB |
| Developer laptops | 8 GB RAM (no CV) | 16 GB |
| Storage | 50 GB free | 200 GB for footage, on an encrypted disk |

Windows hosts need Docker Desktop with WSL2; GPU containers need an NVIDIA driver with WSL2 CUDA support. If that is troublesome, run the CV worker natively in a Python virtual environment — it talks to the API over HTTP either way.

## 5. Deployment procedure (demo)

1. Clone repository; copy `.env.example` → `.env`; generate secrets with the provided script.
2. `docker compose build`.
3. `docker compose up -d postgres api` (migrations run) → create the first admin with the CLI.
4. Load demo venue and event from YAML (`demo/v1.yaml`, `demo/event.yaml`).
5. Copy model artefacts into `models/`; activate one via UI or API.
6. Start `scheduler`, `frontend`, `caddy`, and either `cv-worker` (footage) or the `sim` profile.
7. Smoke test: `GET /api/health` shows `last_prediction_cycle` within 90 s.

## 6. Operations

| Concern | Approach |
|---|---|
| Logs | JSON to stdout; request IDs propagated |
| Health | `/api/health`; scheduler heartbeat each cycle |
| Backups | Nightly `pg_dump` to encrypted drive during data-collection weeks |
| Upgrades | Alembic migrations, backward-compatible within a milestone |
| Demo resilience | Pre-computed observation CSV replayable if the CV worker fails during a presentation |

## 7. Future options (out of scope)

Edge inference next to cameras sending only counts; TimescaleDB; managed PostgreSQL; multiple CV workers per venue.

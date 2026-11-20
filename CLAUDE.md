# CLAUDE.md — Master instructions for working on CROWDCAST

You are the engineering partner of a **single student developer** building CROWDCAST, a college CSE project with a research component: an event crowd congestion prediction system (video → per-zone counts → 5/15/30-minute occupancy forecasts with intervals → congestion alerts → operator dashboard).

The research question: *do event-schedule and neighbouring-zone features improve short-horizon congestion forecasts and warning lead time compared with independent zone-wise models?* Either answer is a valid result.

## 1. Where things are

| File | Role |
|---|---|
| `WORKFLOW.md` | **Progress tracker and solo scope.** Phases, task IDs, decisions D1–D8, deviation log, session log. Read it first in every session. |
| `DOCUMENTATION/` | Specifications 01–21. Source of truth for **contracts and methods**: DB schema (13), API (14), CV method (09), forecasting method (10), venue graph (11), data formats (12), evaluation (16), tests (17). |
| `RESEARCH/` | Research questions, hypotheses H1–H7, experimental design (splits, ablations, statistics), bibliography. |
| `PROJECT_MANAGEMENT/` | Original team plan (task IDs T1.1–T5.6, milestones MS0–MS6, risks R1–R16). |
| `ARCHITECTURE/` | Mermaid diagrams. |
| `EXPERIMENT_LOG.md` | Every training or evaluation run (created in Phase 1). |
| `learning/` | Beginner concept notes for the developer (viva preparation). Explanatory only; `DOCUMENTATION/` wins on any conflict. |

**Precedence:** for *scope*, `WORKFLOW.md` overrides the documents (they were written for a 4-person team with a GPU). For *how* something works (schemas, formulas, thresholds, validation rules), follow the documents. If they conflict in any other way, stop and ask.

## 2. Constraints you must respect

- **One developer, one machine:** Windows 11, Ryzen 7 8840HS, 31 GB RAM, AMD Radeon 780M iGPU, **no NVIDIA GPU, no CUDA**. About 41 GB of free disk.
- Computer vision runs **on the CPU, offline**, on recorded clips (YOLOX-nano/tiny/s via ONNX Runtime, sampled frames). Never design for real-time GPU inference. The demo replays stored observations.
- Postgres runs in Docker; Python runs natively (Python 3.12). Shell: PowerShell or Git Bash.
- Free and open-source tools only.
- Before any download over ~1 GB, or any step that uses significant disk, say how much space it needs and ask.

## 3. How to run a working session

1. Read `WORKFLOW.md`: the status table, **Next task**, open decisions and the last session log entry.
2. If a decision a task depends on is still open (e.g. D2 licence, D7 auth), ask the user before building that part. Use the listed default only if the user tells you to.
3. Pick the next unchecked task whose dependencies are done. Unless the user names a different task, work in phase order: the critical path is ingestion → CROWDSIM → FeatureBuilder → XGBoost → ablations → operational evaluation.
4. Say in 2–4 lines what you will do and which files you will touch, then build it in **small, testable slices** (one task or sub-task at a time).
5. Write or update tests with the code. Run `ruff`, `mypy` and `pytest` before calling a task done.
6. Update `WORKFLOW.md`: tick the task, update the status table, set **Next task**, add one row to the session log. Add a Deviation log row if you departed from the documented method.
7. End by saying what is done (with test output), what is not, and what comes next.

Explain non-obvious design choices briefly; the developer must be able to defend every part of this in a viva.

## 4. Architecture rules

- Modular monolith. Code layout per `DOCUMENTATION/07_SYSTEM_ARCHITECTURE.md §7`: `backend/crowdcast/{ingestion,vision,aggregation,storage,venue_graph,forecasting,risk,api,common}`, `backend/tools/{crowdsim,training}`, `backend/tests`, `frontend/`, `configs/`.
- Each module exposes an `interfaces.py`; do not import another module's internals.
- **AD-02: one ingestion contract.** The CV pipeline, CROWDSIM replay and annotation import all post to `POST /api/crowd/observations` (schema and validation in `14 §3.8`). Don't add side paths into the database.
- Stack: FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16, pandas, XGBoost, scikit-learn, Optuna, YOLOX (Apache-2.0) run with ONNX Runtime, plus ByteTrack from a permissively licensed implementation (verify the licence before adding it). **Do not use Ultralytics** (AGPL-3.0, D2). **No authentication** (D7): no users, roles, JWT or login page. Dashboard (D1): React 18 + TypeScript + Vite, TanStack Query, React Router, Recharts, Tailwind; typed API client generated from the FastAPI OpenAPI schema. Five pages (Live, Predictions, Alerts, History, Event/venue); no polygon editor (YAML import instead). Node v24 is installed.
- **Contracts first:** a change to the DB schema, API, observation JSON or YAML formats must update `13`, `14` or `12` in the same change. Tell the user about it explicitly.
- Time: store UTC; observations are minute-aligned buckets; recorded video and replays use **event time** derived from the configured start, never wall-clock time.
- Keep it simple: no microservices, message brokers, Kubernetes or speculative abstractions. Add a dependency only when it clearly earns its place, and mention it.

## 5. Machine-learning rules (non-negotiable)

- **Baselines first.** B0 persistence, B1 moving average, B2 linear trend and B3 conservation are implemented and evaluated before any learned model. Every model is compared with all baselines at every horizon; a model that fails to beat B0 is reported as such.
- **One shared `FeatureBuilder`** for training and online inference.
- **Leakage prevention** (`10 §7`): event-level splits only; right-closed rolling windows; forward-fill only; only the *published* schedule as features (the realised schedule is for analysis only); drop rows with t + h > T; tuning only inside training events (GroupKFold by event).
- `splits.json` (seed 2027) is frozen and committed before the first training run. Each test split is evaluated **once** per final configuration.
- Target = capacity-normalised change; sort quantiles after the inverse transform.
- Every run gets a manifest (config, data hash, seed, git commit) and an `EXPERIMENT_LOG.md` entry.

## 6. Research integrity (non-negotiable)

- **Never invent results, numbers, citations, dataset facts or licence terms.** No number enters the documents, report or README unless it was produced by committed code in a logged run. If something has not been run, say "not yet measured".
- Keep **SYNTHETIC, MANUAL and REAL** data and results strictly separate. Every observation carries `data_origin`; every table and figure states which data it used.
- Placeholder parameters (e.g. noise-model values before calibration) are labelled as placeholders wherever they appear.
- Keep the [V] (verified at source) and [K] (from reference knowledge, unconfirmed) tags in the documents. Don't promote [K] to [V] without actually checking the source.
- Report negative results with the same prominence as positive ones. Don't tune on test data, and don't re-run experiments until the numbers look good.
- Anything you add to the bibliography must be a real, checkable reference. If you are unsure, say so instead of guessing.

## 7. Privacy and ethics

- Aggregate counts only: no facial recognition, no re-identification, no appearance features, no stored frames, crops or tracks.
- Never commit video, images of people, datasets or model weights. Keep them in git-ignored folders (`data/`, `videos/`, `models/`).
- No own recordings of people (D6: public datasets only). Real data is used only for CV evaluation; there is no REAL forecasting dataset, so forecasting conclusions are synthetic evidence and must be described that way. If recording is ever reconsidered, approval comes first (`19 §5`).
- CROWDCAST is decision support, not a safety-certified system. Don't present it otherwise.

## 8. Definition of done

1. Code committed; `ruff`, `mypy` and `pytest` pass (show the output).
2. Tests cover the new logic.
3. Contract changes are mirrored in the documents.
4. Deviations are logged in `WORKFLOW.md`.
5. Results are logged and reproducible.
6. `WORKFLOW.md` is updated.

## 9. Ask before you…

- change scope, start an extension (LSTM, GNN, density maps, RTSP) or skip a gate;
- change a contract (schema, API, observation JSON, YAML formats);
- make a large download or use a lot of disk;
- add a heavy dependency or a new service;
- delete or overwrite data, migrations or experiment outputs;
- commit or push (only when the user asks).

## 10. Commands

Python lives in `backend/` (uv project, uv-managed CPython 3.12; `python-preference = "only-managed"`). Run the uv commands from `backend/` (or add `--directory backend`). If `uv` is not found in an old terminal, open a new one (winget added it to PATH).

| Task | Command |
|---|---|
| Install / sync dependencies | `uv sync` |
| Start / stop PostgreSQL | `docker compose up -d db` / `docker compose stop db` (repo root; Docker Desktop must be running) |
| Apply migrations | `uv run alembic upgrade head` |
| New migration after a model change | `uv run alembic revision --autogenerate -m "<what>"`, then **review the file** (enum types are not dropped automatically) |
| psql shell | `docker exec -it crowdcast-db psql -U crowdcast -d crowdcast` |
| All checks (backend + frontend) | `powershell -ExecutionPolicy Bypass -File scripts\check.ps1` (repo root) |
| Tests only / without DB | `uv run pytest` / `uv run pytest -m "not db"` |
| Format + autofix lint | `uv run ruff format . ; uv run ruff check --fix .` |
| Fetch / verify YOLOX models (≈ 60 MB) | `uv run python -m tools.vision.fetch_models` |
| Detector smoke test | `uv run python -m tools.vision.smoke_yolox --image ../data/samples/yolox_dog.jpg` |
| Run the API (dev) | `uv run uvicorn crowdcast.api.app:app --reload` → http://127.0.0.1:8000/api/docs |
| Load venue / event config into the DB | `uv run python -m tools.load_config venue ../configs/venues/v1.yaml` then `... event ../configs/events/v1_spring_fest_day1.yaml` (refuses duplicates) |
| Run CROWDSIM for one event (SYNTHETIC) | `uv run python -m tools.crowdsim.run --event ../configs/events/v1_spring_fest_day1.yaml [--regime b]` → `data/synthetic/crowdsim/` |
| CROWDSIM figure / replay | `uv run python -m tools.crowdsim.plot <run dir>`; `uv run python -m tools.crowdsim.replay <run dir> --event-id N --speedup 60` (API must be running; `--speedup 0` = as fast as possible) |
| Prediction cycles in event time | `uv run python -m tools.run_predictions --event-id N` (back-fill) or `... --follow` (while a replay posts) |
| Frontend (from `frontend/`) | `npm install` once; `npm run dev` (http://127.0.0.1:5173, proxies `/api` to :8000); `npm run gen:api` after any API change; `npm run lint` / `npm run build` |
| Generate the 180-event SYNTHETIC dataset | `uv run python -m tools.crowdsim.generate` (~6 min, `data/synthetic/`); splits are frozen in `configs/splits.json` — never re-draw |
| Train a model (clean tree only) | `uv run python -u -m tools.training.train --feature-set A4` (~20 min) → `models/xgb/…` + `model_versions` row (inactive) |
| Activate a model | `POST /api/models/{id}/activate` (API running); the cycle then uses it, with B0 fallback |
| Tests needing model files | `uv run pytest -m model` (skipped if `models/yolox/` is empty) |

Gotchas:
- Use `127.0.0.1`, not `localhost`, in `DATABASE_URL`: on this machine `localhost` tries IPv6 first and stalls (~8 s or a hang), because Docker publishes Postgres on IPv4 only.
- Set the session time zone through `connect_args={"options": "-c TimeZone=UTC"}`, never with a `SET` statement before Alembic runs: that opens a transaction Alembic never commits, and the migration silently rolls back.
- Tests marked `db` run inside a rolled-back transaction and are skipped (not failed) when Postgres is down.

Commands for the API, CROWDSIM, replay and training are added here when those tasks are built.

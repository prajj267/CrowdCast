"""FastAPI application (WORKFLOW 2.3.2; doc 14).

Run (from backend/):  uv run uvicorn crowdcast.api.app:app --reload
OpenAPI docs: http://127.0.0.1:8000/api/docs
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from importlib.metadata import version
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.engine import Engine

from crowdcast.api import (
    routes_alerts,
    routes_crowd,
    routes_events,
    routes_models,
    routes_predictions,
    routes_venues,
)
from crowdcast.api.errors import install_error_handlers
from crowdcast.common.config import get_settings
from crowdcast.storage.interfaces import check_database, get_engine

API_VERSION = version("crowdcast")


class Health(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["ok", "error"]
    last_prediction_cycle: datetime | None  # latest predictions.issued_at; null before any cycle
    version: str


def engine_dependency() -> Engine:
    """Overridable in tests (app.dependency_overrides)."""
    return get_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CROWDCAST API",
        version=API_VERSION,
        docs_url="/api/docs",  # doc 14 header
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A request id ties a client-visible error to the server log line (doc 14 §1.1).
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request.state.request_id)
        return response

    install_error_handlers(app)
    app.include_router(routes_venues.router)
    app.include_router(routes_events.router)
    app.include_router(routes_crowd.router)
    app.include_router(routes_predictions.router)
    app.include_router(routes_alerts.router)
    app.include_router(routes_models.router)

    @app.get("/api/health", response_model=Health, tags=["system"])
    def health(response: Response, engine: Annotated[Engine, Depends(engine_dependency)]) -> Health:
        """Liveness and database check (doc 14 §3.16). 503 when the database is unreachable."""
        try:
            last = check_database(engine)
        except Exception:
            response.status_code = 503
            return Health(
                status="error", db="error", last_prediction_cycle=None, version=API_VERSION
            )
        return Health(status="ok", db="ok", last_prediction_cycle=last, version=API_VERSION)

    return app


app = create_app()

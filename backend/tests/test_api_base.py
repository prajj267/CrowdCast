"""API skeleton tests: health endpoint and error envelope (task 2.3.2; doc 14 §1.1, §3.16)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from crowdcast.api.app import API_VERSION, create_app, engine_dependency
from crowdcast.api.errors import ApiError


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


def _app_with_test_routes() -> FastAPI:
    app = create_app()

    @app.post("/test/echo")
    def echo(body: _Body) -> _Body:
        return body

    @app.get("/test/conflict")
    def conflict() -> None:
        raise ApiError(409, "CONFLICT", "already exists", [{"field": "name", "issue": "taken"}])

    @app.get("/test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    # raise_server_exceptions=False: let the 500 handler answer, as in production
    with TestClient(_app_with_test_routes(), raise_server_exceptions=False) as c:
        yield c


def _assert_envelope(resp: object, status: int, code: str) -> dict[str, object]:
    from httpx import Response

    assert isinstance(resp, Response)
    assert resp.status_code == status
    err = resp.json()["error"]
    assert err["code"] == code
    assert set(err) == {"code", "message", "details", "request_id"}
    uuid.UUID(err["request_id"])  # a real UUID
    assert resp.headers["X-Request-ID"] == err["request_id"]
    return dict(err)


# ------------------------------------------------------------------ error envelope
def test_unknown_route_is_enveloped_404(client: TestClient) -> None:
    _assert_envelope(client.get("/api/nope"), 404, "NOT_FOUND")


def test_validation_error_lists_fields(client: TestClient) -> None:
    err = _assert_envelope(
        client.post("/test/echo", json={"count": "many", "extra": 1}), 422, "VALIDATION_ERROR"
    )
    fields = {d["field"] for d in err["details"]}  # type: ignore[attr-defined]
    assert fields == {"count", "extra"}  # unknown fields are rejected too (doc 14 §1)


def test_malformed_json_is_400(client: TestClient) -> None:
    resp = client.post(
        "/test/echo", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    _assert_envelope(resp, 400, "BAD_REQUEST")


def test_api_error_passes_code_and_details(client: TestClient) -> None:
    err = _assert_envelope(client.get("/test/conflict"), 409, "CONFLICT")
    assert err["message"] == "already exists"
    assert err["details"] == [{"field": "name", "issue": "taken"}]


def test_unhandled_error_hides_details(client: TestClient) -> None:
    resp = client.get("/test/boom")
    err = _assert_envelope(resp, 500, "INTERNAL_ERROR")
    assert "secret" not in resp.text
    assert err["details"] == []


def test_successful_response_has_request_id(client: TestClient) -> None:
    resp = client.post("/test/echo", json={"count": 3})
    assert resp.status_code == 200 and resp.json() == {"count": 3}
    uuid.UUID(resp.headers["X-Request-ID"])


# ------------------------------------------------------------------ health
def test_health_reports_db_down_as_503() -> None:
    app = create_app()
    dead: Engine = create_engine(
        "postgresql+psycopg://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )
    app.dependency_overrides[engine_dependency] = lambda: dead
    with TestClient(app) as c:
        resp = c.get("/api/health")
    assert resp.status_code == 503
    assert resp.json() == {
        "status": "error",
        "db": "error",
        "last_prediction_cycle": None,
        "version": API_VERSION,
    }


@pytest.mark.db
def test_health_ok_with_database(db_engine: Engine) -> None:
    app = create_app()
    app.dependency_overrides[engine_dependency] = lambda: db_engine
    with TestClient(app) as c:
        resp = c.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert (body["status"], body["db"], body["version"]) == ("ok", "ok", API_VERSION)

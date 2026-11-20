"""Uniform error envelope for every API error (doc 14 §1.1).

    {"error": {"code": ..., "message": ..., "details": [...], "request_id": ...}}

No authentication exists (decision D7), so 401 UNAUTHENTICATED, 403 FORBIDDEN and
429 RATE_LIMITED are not produced.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("crowdcast.api")

CODE_BY_STATUS = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class ApiError(Exception):
    """Raise from a route to return an enveloped error, e.g. ApiError(409, "CONFLICT", ...)."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def request_id_of(request: Request) -> str:
    return str(getattr(request.state, "request_id", ""))


def envelope(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    rid = request_id_of(request)
    body = {
        "error": {"code": code, "message": message, "details": details or [], "request_id": rid}
    }
    return JSONResponse(body, status_code=status_code, headers={"X-Request-ID": rid})


async def _api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return envelope(request, exc.status_code, exc.code, exc.message, exc.details)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = CODE_BY_STATUS.get(exc.status_code, "ERROR")
    return envelope(request, exc.status_code, code, str(exc.detail))


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    if any(e.get("type") == "json_invalid" for e in errors):
        return envelope(request, 400, "BAD_REQUEST", "request body is not valid JSON")
    details = [
        {
            "field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
            "issue": e.get("msg", ""),
        }
        for e in errors
    ]
    message = details[0]["issue"] if len(details) == 1 else f"{len(details)} validation errors"
    return envelope(request, 422, "VALIDATION_ERROR", message, details)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Details are logged with the request id, never returned to the client.
    log.exception("unhandled error (request_id=%s)", request_id_of(request), exc_info=exc)
    return envelope(request, 500, "INTERNAL_ERROR", "internal server error")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)

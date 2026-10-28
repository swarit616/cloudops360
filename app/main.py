"""CloudOps360 FastAPI application factory.

Run with: ``uvicorn app.main:create_app --factory``
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import cloud, diagnostics, remediation, routes
from app.container import AppContainer, build_container
from app.logging_config import configure_logging, get_logger, log_event, request_id_var

logger = get_logger("http")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_QUIET_PATHS = {"/metrics", "/health"}


def _error_body(status_code: int, message: str) -> dict[str, Any]:
    try:
        error = HTTPStatus(status_code).phrase.lower().replace(" ", "_")
    except ValueError:
        error = "error"
    return {"error": error, "message": message, "request_id": request_id_var.get()}


def create_app(container: AppContainer | None = None) -> FastAPI:
    """Build the FastAPI app. Pass a container in tests to inject fakes."""
    container = container or build_container()
    configure_logging(container.settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        container.refresher.start()
        log_event(logger, logging.INFO, "app.started", version=__version__, **container.settings.public_dict())
        yield
        container.refresher.stop()
        log_event(logger, logging.INFO, "app.stopped")

    app = FastAPI(
        title="CloudOps360",
        description="Multi-cloud monitoring, diagnostics and safe auto-remediation.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.container = container

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID_RE.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:  # noqa: BLE001 - never leak internals to the client
                log_event(
                    logger,
                    logging.ERROR,
                    "http.unhandled_exception",
                    error_type=type(exc).__name__,
                    path=request.url.path,
                )
                response = JSONResponse(
                    status_code=500,
                    content=_error_body(500, "An unexpected error occurred"),
                )
            duration = time.perf_counter() - started
            route = request.scope.get("route")
            path_label = getattr(route, "path", "unmatched")
            container.metrics.record_http(request.method, path_label, response.status_code, duration)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            log_event(
                logger,
                logging.DEBUG if request.url.path in _QUIET_PATHS else logging.INFO,
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round(duration * 1000, 1),
            )
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.status_code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        body = _error_body(422, "Invalid request")
        body["details"] = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content=body)

    for router in (routes.router, diagnostics.router, remediation.router, cloud.router):
        app.include_router(router)
    return app

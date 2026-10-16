"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_allowed(request: Request, allowed_origins: list[str]) -> bool:
    """Reject cross-site state-changing requests.

    Browsers send an Origin header on POST/PATCH/DELETE. It must be one of the configured origins, or the same
    host the request was addressed to (which is how the Vite dev proxy forwards requests). Requests without an
    Origin header (for example scripts or curl) are allowed, because they cannot carry a victim's cookie from
    another website's page.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return True
    if origin in allowed_origins:
        return True
    host = request.headers.get("host", "")
    return urlsplit(origin).netloc == host


def create_app() -> FastAPI:
    settings = get_settings()
    # The interactive API schema is useful in development but is not published in production.
    docs_enabled = settings.app_env != "production"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.middleware("http")
    async def request_guards(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        declared = request.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > settings.max_request_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        if request.method in UNSAFE_METHODS and not _origin_allowed(request, settings.cors_origins):
            return JSONResponse(status_code=403, content={"detail": "Cross-site request rejected."})
        return await call_next(request)

    app.include_router(api_router)
    return app


app = create_app()

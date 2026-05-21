"""
MedAxis — Shared FastAPI middleware and exception handlers.

Usage in each service main.py:
    from middleware import add_middleware, add_exception_handlers

    add_middleware(app, service_name="auth-service")
    add_exception_handlers(app)
"""
import uuid
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

try:
    from medaxis_logging import correlation_id_var
except ImportError:
    from contextvars import ContextVar
    correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

logger = logging.getLogger(__name__)


def add_middleware(app: FastAPI, service_name: str) -> None:
    """Add correlation ID middleware to a FastAPI app."""

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next) -> Response:
        # Extract or generate correlation ID
        corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        correlation_id_var.set(corr_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response


def add_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers that return structured JSON."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        corr_id = correlation_id_var.get("-")
        errors = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            errors.append({"field": field, "message": err.get("msg", ""), "type": err.get("type", "")})
        return JSONResponse(
            status_code=422,
            content={"detail": errors, "correlation_id": corr_id},
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        corr_id = correlation_id_var.get("-")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "correlation_id": corr_id},
            headers={"X-Correlation-ID": corr_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        corr_id = correlation_id_var.get("-")
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            extra={"correlation_id": corr_id, "path": str(request.url)},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error. Please try again or contact support.",
                "correlation_id": corr_id,
            },
            headers={"X-Correlation-ID": corr_id},
        )

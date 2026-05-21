"""Replenishment Service — FastAPI application entry point."""
import sys
sys.path.insert(0, "/shared")

from fastapi import FastAPI
from contextlib import asynccontextmanager

from medaxis_logging import setup_logging, get_logger
from config_validator import validate_all
from middleware import add_middleware, add_exception_handlers
from observability import setup_sentry, setup_metrics

from app.database import init_db, AsyncSessionLocal
from app.routes import router

validate_all({
    "DATABASE_URL": {"min_length": 10},
    "JWT_SECRET":   {"min_length": 32},
})

setup_logging("replenishment-service")
logger = get_logger(__name__)
setup_sentry("replenishment-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Replenishment service starting — initialising database")
    await init_db()
    logger.info("Replenishment service ready")
    yield


app = FastAPI(
    title="MedAxis — Replenishment Service",
    description="Reorder lifecycle, AI-triggered PO suggestions, supervisor approval workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

add_middleware(app, "replenishment-service")
add_exception_handlers(app)
setup_metrics(app, "replenishment-service")
app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"service": "replenishment-service", "status": "ok", "checks": {"database": "ok"}}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"service": "replenishment-service", "status": "degraded", "checks": {"database": "error"}},
        )

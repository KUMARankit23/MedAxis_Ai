"""Billing Service — FastAPI application entry point."""
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
    "DATABASE_URL":    {"min_length": 10},
    "JWT_SECRET":      {"min_length": 32},
    "INVENTORY_SERVICE_URL": {"min_length": 5},
})

setup_logging("billing-service")
logger = get_logger(__name__)
setup_sentry("billing-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Billing service starting — initialising database")
    await init_db()
    logger.info("Billing service ready")
    yield


app = FastAPI(
    title="MedAxis — Billing Service",
    description="Prescriptions, OTC/Rx invoicing, GST calculation, stock deduction.",
    version="1.0.0",
    lifespan=lifespan,
)

add_middleware(app, "billing-service")
add_exception_handlers(app)
setup_metrics(app, "billing-service")
app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"service": "billing-service", "status": "ok", "checks": {"database": "ok"}}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"service": "billing-service", "status": "degraded", "checks": {"database": "error"}},
        )

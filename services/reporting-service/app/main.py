"""Reporting Service — FastAPI application entry point."""
import sys
sys.path.insert(0, "/shared")

from fastapi import FastAPI

from medaxis_logging import setup_logging, get_logger
from config_validator import validate_all
from middleware import add_middleware, add_exception_handlers
from observability import setup_sentry, setup_metrics

from app.routes import router

validate_all({
    "BILLING_DB_URL":   {"min_length": 10},
    "INVENTORY_DB_URL": {"min_length": 10},
    "JWT_SECRET":       {"min_length": 32},
})

setup_logging("reporting-service")
logger = get_logger(__name__)
setup_sentry("reporting-service")

app = FastAPI(
    title="MedAxis — Reporting Service",
    description="BI dashboards, sales analytics, store performance, inventory reports.",
    version="1.0.0",
)

add_middleware(app, "reporting-service")
add_exception_handlers(app)
setup_metrics(app, "reporting-service")
app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    """Health check — verifies billing and inventory DB connectivity."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from app.config import BILLING_DB_URL, INVENTORY_DB_URL
    checks = {}
    overall = "ok"
    for name, url in [("billing_db", BILLING_DB_URL), ("inventory_db", INVENTORY_DB_URL)]:
        try:
            eng = create_async_engine(
                url.replace("postgresql://", "postgresql+asyncpg://"),
                pool_pre_ping=True,
            )
            async with eng.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await eng.dispose()
            checks[name] = "ok"
        except Exception as e:
            checks[name] = "error"
            overall = "degraded"
            logger.error(f"Health check {name} failed: {e}")

    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=200 if overall == "ok" else 503,
        content={"service": "reporting-service", "status": overall, "checks": checks},
    )

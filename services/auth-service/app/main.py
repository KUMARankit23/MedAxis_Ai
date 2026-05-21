"""Auth Service — FastAPI application entry point."""
import sys
import os

# Add shared utilities to path
sys.path.insert(0, "/shared")

from fastapi import FastAPI
from contextlib import asynccontextmanager

from medaxis_logging import setup_logging, get_logger
from config_validator import validate_all
from middleware import add_middleware, add_exception_handlers
from observability import setup_sentry, setup_metrics

from app.database import init_db, AsyncSessionLocal
from app.service import seed_admin
from app.routes import router

# ── Validate required secrets at startup ─────────────────────────────────────
validate_all({
    "DATABASE_URL": {"min_length": 10},
    "JWT_SECRET":   {"min_length": 32},
})

# ── Structured logging ────────────────────────────────────────────────────────
setup_logging("auth-service")
logger = get_logger(__name__)
setup_sentry("auth-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auth service starting — initialising database")
    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_admin(db)
    logger.info("Auth service ready")
    yield
    logger.info("Auth service shutting down")


app = FastAPI(
    title="MedAxis — Auth Service",
    description="JWT authentication, RBAC, user management, and audit logging.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

add_middleware(app, "auth-service")
add_exception_handlers(app)
setup_metrics(app, "auth-service")
app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    """Health check with DB connectivity verification."""
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"service": "auth-service", "status": "ok", "checks": {"database": "ok"}}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"service": "auth-service", "status": "degraded", "checks": {"database": "error"}},
        )

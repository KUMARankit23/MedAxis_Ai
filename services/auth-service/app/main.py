"""Auth Service — FastAPI application entry point."""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import init_db
from app.service import seed_admin
from app.database import AsyncSessionLocal
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed default admin
    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_admin(db)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="MedAxis — Auth Service",
    description="JWT authentication, RBAC, user management, and audit logging.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    return {"service": "auth-service", "status": "ok"}

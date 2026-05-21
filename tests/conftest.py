"""
Shared pytest fixtures for MedAxis service tests.
Uses SQLite in-memory databases — no real PostgreSQL needed.
"""
import sys
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

# ── Test environment variables ────────────────────────────────────────────────
os.environ.setdefault("DATABASE_URL",    "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("JWT_SECRET",      "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("REDIS_HOST",      "localhost")
os.environ.setdefault("REDIS_PORT",      "6379")
os.environ.setdefault("ENVIRONMENT",     "test")
os.environ.setdefault("SENTRY_DSN",      "")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault("INVENTORY_SERVICE_URL", "http://localhost:8002")
os.environ.setdefault("BILLING_DB_URL",   "sqlite+aiosqlite:///./test_billing.db")
os.environ.setdefault("INVENTORY_DB_URL", "sqlite+aiosqlite:///./test_inventory.db")


def make_test_engine(url: str = "sqlite+aiosqlite:///:memory:"):
    return create_async_engine(url, echo=False, connect_args={"check_same_thread": False})


def make_test_session(engine):
    return sessionmaker(bind=engine, class_=AsyncSession,
                        autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

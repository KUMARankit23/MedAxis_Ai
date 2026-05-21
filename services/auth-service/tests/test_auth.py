"""
Auth Service — critical path tests.
Runnable via: pytest services/ OR pytest tests/
Uses SQLite in-memory DB — no real PostgreSQL needed.
"""
import sys
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Path setup ────────────────────────────────────────────────────────────────
_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..")
_SHARED_DIR  = os.path.join(_SERVICE_DIR, "..", "..", "shared")
for p in (_SHARED_DIR, _SERVICE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# Clear cached app modules from other service tests
for m in list(sys.modules.keys()):
    if m == "app" or m.startswith("app."):
        del sys.modules[m]

os.environ.setdefault("DATABASE_URL",    "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET",      "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("REDIS_HOST",      "localhost")
os.environ.setdefault("REDIS_PORT",      "6379")
os.environ.setdefault("ENVIRONMENT",     "test")
os.environ.setdefault("SENTRY_DSN",      "")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

from app.database import Base, get_db  # noqa: E402
from app.main import app               # noqa: E402
from app.service import seed_admin     # noqa: E402

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(
    TEST_DB_URL, echo=False, poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = sessionmaker(
    bind=engine, class_=AsyncSession,
    autocommit=False, autoflush=False, expire_on_commit=False,
)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as db:
        await seed_admin(db)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    resp = await client.post("/auth/login", json={"username": "nobody", "password": "anything"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    login = await client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    token = login.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_me_without_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh(client):
    login = await client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    refresh_token = login.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    assert "service" in resp.json()


@pytest.mark.asyncio
async def test_create_user_requires_admin(client):
    resp = await client.post("/auth/users", json={
        "username": "newuser", "email": "new@test.com",
        "password": "Test@1234", "role": "pharmacist",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_user_as_admin(client):
    login = await client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    token = login.json()["access_token"]
    resp = await client.post("/auth/users", json={
        "username": "testpharmacist",
        "email": "testph@medaxis.com",
        "password": "Pharma@123",
        "role": "pharmacist",
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["username"] == "testpharmacist"
    assert resp.json()["role"] == "pharmacist"

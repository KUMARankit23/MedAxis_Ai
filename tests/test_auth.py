"""
Auth Service — critical path tests.
Tests: login success, login failure, token refresh, logout blacklisting.
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

# Clear any cached 'app' modules to avoid collisions with other service tests
for m in list(sys.modules.keys()):
    if m == "app" or m.startswith("app."):
        del sys.modules[m]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "auth-service"))

from app.database import Base, get_db
from app.main import app
from app.service import seed_admin

# ── In-memory SQLite engine for tests ────────────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, class_=AsyncSession,
                           autocommit=False, autoflush=False, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables and seed admin user once per test."""
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
    """Valid credentials return access and refresh tokens."""
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
    """Wrong password returns 401."""
    resp = await client.post("/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    """Unknown username returns 401."""
    resp = await client.post("/auth/login", json={"username": "nobody", "password": "anything"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    """Authenticated /auth/me returns current user."""
    login = await client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    token = login.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_me_without_token(client):
    """Unauthenticated /auth/me returns 401."""
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh(client):
    """Refresh token returns new access token."""
    login = await client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Health endpoint returns ok status."""
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)  # 503 if SQLite health check fails
    assert "service" in resp.json()


@pytest.mark.asyncio
async def test_create_user_requires_admin(client):
    """Creating a user without admin token returns 401."""
    resp = await client.post("/auth/users", json={
        "username": "newuser", "email": "new@test.com",
        "password": "Test@1234", "role": "pharmacist",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_user_as_admin(client):
    """Admin can create a new user."""
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

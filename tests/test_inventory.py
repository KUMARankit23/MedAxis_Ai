"""
Inventory Service — critical path tests.
Tests: medicine creation, batch receive, stock deduction (success + insufficient).
"""
import sys
import os
import pytest
import pytest_asyncio
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from fastapi import Request
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Clear any cached 'app' modules to avoid collisions with other service tests
for m in list(sys.modules.keys()):
    if m == "app" or m.startswith("app."):
        del sys.modules[m]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "inventory-service"))

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, class_=AsyncSession,
                           autocommit=False, autoflush=False, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

# ── Mock JWT auth — bypass token validation in tests ─────────────────────────
from app.routes import get_current_user as inventory_get_current_user


def mock_get_current_user(request: Request = None):
    return {"sub": "test-user-id", "role": "admin", "username": "testadmin", "outlet_id": None}


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    # Patch auth for all inventory tests
    app.dependency_overrides[inventory_get_current_user] = mock_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(inventory_get_current_user, None)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_medicine(client):
    """Create a medicine and verify it's returned."""
    resp = await client.post("/inventory/medicines", json={
        "name": "Paracetamol 500mg",
        "category": "OTC",
        "unit_price": 2.50,
        "reorder_level": 50,
        "reorder_quantity": 200,
        "unit": "tablets",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Paracetamol 500mg"
    assert data["category"] == "OTC"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_medicines(client):
    """List medicines returns paginated result."""
    resp = await client.get("/inventory/medicines")
    assert resp.status_code == 200
    data = resp.json()
    assert "medicines" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_receive_batch_and_deduct(client):
    """Receive stock then deduct — verify quantities are correct."""
    # Create medicine
    med_resp = await client.post("/inventory/medicines", json={
        "name": "Ibuprofen 400mg",
        "category": "OTC",
        "unit_price": 3.50,
        "reorder_level": 20,
        "reorder_quantity": 100,
    })
    assert med_resp.status_code == 201
    med_id = med_resp.json()["id"]

    # Receive 100 units
    expiry = (date.today() + timedelta(days=365)).isoformat()
    batch_resp = await client.post("/inventory/batches", json={
        "medicine_id": med_id,
        "batch_number": "BATCH-TEST-001",
        "outlet_id": "OUTLET-001",
        "quantity": 100,
        "expiry_date": expiry,
    })
    assert batch_resp.status_code == 201

    # Deduct 30 units
    deduct_resp = await client.post("/inventory/deduct", json={
        "medicine_id": med_id,
        "outlet_id": "OUTLET-001",
        "quantity": 30,
        "reference_id": "TEST-INV-001",
    })
    assert deduct_resp.status_code == 200
    assert deduct_resp.json()["deducted"] == 30
    assert deduct_resp.json()["remaining_stock"] == 70


@pytest.mark.asyncio
async def test_deduct_insufficient_stock(client):
    """Deducting more than available stock returns 409."""
    # Create medicine with no stock
    med_resp = await client.post("/inventory/medicines", json={
        "name": "Rare Medicine",
        "category": "PRESCRIPTION",
        "unit_price": 100.0,
        "reorder_level": 5,
        "reorder_quantity": 20,
    })
    med_id = med_resp.json()["id"]

    # Try to deduct without any stock
    resp = await client.post("/inventory/deduct", json={
        "medicine_id": med_id,
        "outlet_id": "OUTLET-001",
        "quantity": 10,
        "reference_id": "TEST-FAIL-001",
    })
    assert resp.status_code == 409
    assert "Insufficient stock" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_expiry_alerts(client):
    """Expiry alerts endpoint returns list."""
    resp = await client.get("/inventory/alerts/expiring?days=30")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_low_stock_alerts(client):
    """Low stock alerts endpoint returns structured response."""
    resp = await client.get("/inventory/alerts/low-stock")
    assert resp.status_code == 200
    assert "low_stock_items" in resp.json()

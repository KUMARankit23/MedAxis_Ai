"""
Billing Service — critical path tests.
Tests: invoice creation (draft), invoice totals, cancel draft invoice.
Note: confirm invoice calls inventory service (mocked).
"""
import sys
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "billing-service"))

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

from app.routes import get_current_user as billing_get_current_user


def mock_get_current_user(request: Request = None):
    return {"sub": "test-user-id", "role": "admin", "username": "testadmin", "outlet_id": "OUTLET-001"}


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[billing_get_current_user] = mock_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(billing_get_current_user, None)


SAMPLE_INVOICE = {
    "outlet_id": "OUTLET-001",
    "patient_name": "Test Patient",
    "payment_method": "CASH",
    "items": [
        {
            "medicine_id": "00000000-0000-0000-0000-000000000001",
            "medicine_name": "Paracetamol 500mg",
            "quantity": 10,
            "unit_price": 2.50,
            "category": "OTC",
        }
    ],
}


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_invoice_draft(client):
    """Creating an invoice returns a DRAFT with correct totals."""
    resp = await client.post("/billing/invoices", json=SAMPLE_INVOICE)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["outlet_id"] == "OUTLET-001"
    assert data["patient_name"] == "Test Patient"
    # subtotal = 10 * 2.50 = 25.00, tax = 25 * 0.05 = 1.25, total = 26.25
    assert abs(data["subtotal"] - 25.0) < 0.01
    assert abs(data["tax"] - 1.25) < 0.01
    assert abs(data["total"] - 26.25) < 0.01
    assert "invoice_number" in data
    assert data["invoice_number"].startswith("INV-")


@pytest.mark.asyncio
async def test_list_invoices(client):
    """List invoices returns paginated result."""
    resp = await client.get("/billing/invoices")
    assert resp.status_code == 200
    data = resp.json()
    assert "invoices" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_invoice_by_id(client):
    """Get a specific invoice by ID."""
    create_resp = await client.post("/billing/invoices", json=SAMPLE_INVOICE)
    invoice_id = create_resp.json()["id"]

    resp = await client.get(f"/billing/invoices/{invoice_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == invoice_id


@pytest.mark.asyncio
async def test_cancel_draft_invoice(client):
    """Cancelling a DRAFT invoice sets status to CANCELLED."""
    create_resp = await client.post("/billing/invoices", json=SAMPLE_INVOICE)
    invoice_id = create_resp.json()["id"]

    cancel_resp = await client.post(f"/billing/invoices/{invoice_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["message"] == "Invoice cancelled"


@pytest.mark.asyncio
async def test_invoice_items_not_empty(client):
    """Invoice with empty items list returns 422."""
    resp = await client.post("/billing/invoices", json={
        "outlet_id": "OUTLET-001",
        "payment_method": "CASH",
        "items": [],
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_confirm_invoice_calls_inventory(client):
    """Confirming an invoice calls inventory deduct (mocked) and sets CONFIRMED."""
    create_resp = await client.post("/billing/invoices", json=SAMPLE_INVOICE)
    invoice_id = create_resp.json()["id"]

    # Mock the httpx call to inventory service
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"deducted": 10, "remaining_stock": 90}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        resp = await client.post(
            f"/billing/invoices/{invoice_id}/confirm",
            headers={"Authorization": "Bearer fake-token-for-test"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_invoice_stats(client):
    """Invoice stats endpoint returns revenue metrics."""
    resp = await client.get("/billing/invoices/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_revenue" in data
    assert "invoice_count" in data

"""Billing Service — FastAPI routes."""
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models import Invoice, InvoiceStatus
from app.schemas import InvoiceCreate, InvoiceResponse, PrescriptionCreate, PrescriptionResponse
from app.service import create_invoice, confirm_invoice, refund_invoice, create_prescription
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

router = APIRouter()


def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        p = pyjwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if p.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return p
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"Required roles: {list(roles)}")
        return user
    return dep


# ── Prescriptions ─────────────────────────────────────────────────────────────

@router.post("/billing/prescriptions", response_model=PrescriptionResponse, status_code=201, tags=["Prescriptions"])
async def add_prescription(
    body: PrescriptionCreate,
    user=Depends(require_role("admin", "pharmacist")),
    db: AsyncSession = Depends(get_db),
):
    return await create_prescription(db, body, user["sub"])


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.post("/billing/invoices", response_model=InvoiceResponse, status_code=201, tags=["Invoices"])
async def create(
    body: InvoiceCreate,
    user=Depends(require_role("admin", "pharmacist")),
    db: AsyncSession = Depends(get_db),
):
    return await create_invoice(db, body, user["sub"])


@router.post("/billing/invoices/{invoice_id}/confirm", response_model=InvoiceResponse, tags=["Invoices"])
async def confirm(
    invoice_id: str,
    request: Request,
    user=Depends(require_role("admin", "pharmacist")),
    db: AsyncSession = Depends(get_db),
):
    token = request.headers.get("Authorization", "").split(" ", 1)[-1]
    try:
        return await confirm_invoice(db, invoice_id, token)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/invoices/{invoice_id}/cancel", tags=["Invoices"])
async def cancel(
    invoice_id: str,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    if isinstance(invoice_id, str):
        try:
            invoice_id = uuid.UUID(invoice_id)
        except ValueError:
            pass
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.confirmed:
        raise HTTPException(status_code=400, detail="Use /refund for confirmed invoices")
    inv.status = InvoiceStatus.cancelled
    await db.commit()
    return {"message": "Invoice cancelled", "invoice_id": invoice_id}


@router.post("/billing/invoices/{invoice_id}/refund", tags=["Invoices"])
async def refund(
    invoice_id: str,
    request: Request,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    token = request.headers.get("Authorization", "").split(" ", 1)[-1]
    try:
        inv = await refund_invoice(db, invoice_id, token)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Invoice refunded and stock restored", "refunded_amount": inv.total}


@router.get("/billing/invoices/stats", tags=["Invoices"])
async def invoice_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns total revenue, invoice count, and average invoice value for a date range."""
    q = select(
        func.count(Invoice.id).label("invoice_count"),
        func.coalesce(func.sum(Invoice.total), 0).label("total_revenue"),
        func.coalesce(func.avg(Invoice.total), 0).label("avg_value"),
    ).where(Invoice.status == InvoiceStatus.confirmed)

    if start_date:
        q = q.where(func.date(Invoice.created_at) >= start_date)
    if end_date:
        q = q.where(func.date(Invoice.created_at) <= end_date)

    result = await db.execute(q)
    row = result.one()
    return {
        "total_revenue": round(float(row.total_revenue), 2),
        "invoice_count": row.invoice_count,
        "avg_value": round(float(row.avg_value), 2),
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }


def _apply_invoice_filters(q, outlet_id, status, patient_name, invoice_number, date_from, date_to):
    """Helper to apply common invoice filters to a query."""
    if outlet_id:
        q = q.where(Invoice.outlet_id == outlet_id)
    if status:
        q = q.where(Invoice.status == status.upper())
    if patient_name:
        q = q.where(Invoice.patient_name.ilike(f"%{patient_name}%"))
    if invoice_number:
        q = q.where(Invoice.invoice_number.ilike(f"%{invoice_number}%"))
    if date_from:
        q = q.where(func.date(Invoice.created_at) >= date_from)
    if date_to:
        q = q.where(func.date(Invoice.created_at) <= date_to)
    return q


@router.get("/billing/invoices", tags=["Invoices"])
async def list_invoices(
    outlet_id: Optional[str] = None,
    status: Optional[str] = None,
    patient_name: Optional[str] = None,
    invoice_number: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Count query
    count_q = _apply_invoice_filters(
        select(func.count(Invoice.id)),
        outlet_id, status, patient_name, invoice_number, date_from, date_to,
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Data query with pagination
    data_q = _apply_invoice_filters(
        select(Invoice).options(selectinload(Invoice.items)),
        outlet_id, status, patient_name, invoice_number, date_from, date_to,
    )
    offset = (page - 1) * page_size
    data_q = data_q.order_by(Invoice.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(data_q)
    invoices = [InvoiceResponse.model_validate(i) for i in result.scalars().all()]

    return {
        "invoices": [i.model_dump() for i in invoices],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/billing/invoices/{invoice_id}", response_model=InvoiceResponse, tags=["Invoices"])
async def get_invoice(
    invoice_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    if isinstance(invoice_id, str):
        try:
            invoice_id = uuid.UUID(invoice_id)
        except ValueError:
            pass
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return InvoiceResponse.model_validate(inv)

"""Inventory Service — FastAPI routes."""
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, field_validator
from app.database import get_db
from app.models import Medicine, InventoryBatch, StockLedger
from app.schemas import (MedicineCreate, MedicineResponse, BatchCreate, BatchResponse,
                          StockDeductRequest, AdjustRequest, StockLevelResponse,
                          ExpiryAlertResponse, LedgerResponse)
from app.service import (create_medicine, list_medicines, receive_batch,
                          deduct_stock, adjust_stock, get_expiry_alerts, get_total_stock)
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt


# ── Typed schemas for previously untyped endpoints ────────────────────────────

class StockTransferRequest(BaseModel):
    medicine_id: str
    from_outlet_id: str
    to_outlet_id: str
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    model_config = {"str_strip_whitespace": True}


class QuarantineRequest(BaseModel):
    reason: Optional[str] = "No reason provided"

    model_config = {"str_strip_whitespace": True}

router = APIRouter()


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = pyjwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles):
    def dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"Required roles: {list(roles)}")
        return user
    return dep


# ── Medicines ─────────────────────────────────────────────────────────────────

@router.get("/inventory/medicines", tags=["Medicines"])
async def list_meds(
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Build base query for count and data
    q = select(Medicine)
    if category:
        q = q.where(Medicine.category == category)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                Medicine.name.ilike(pattern),
                Medicine.generic_name.ilike(pattern),
            )
        )

    # Total count
    count_q = select(func.count()).select_from(q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginated data
    offset = (page - 1) * page_size
    q = q.order_by(Medicine.name).offset(offset).limit(page_size)
    result = await db.execute(q)
    medicines = result.scalars().all()

    return {
        "medicines": [MedicineResponse.model_validate(m).model_dump() for m in medicines],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/inventory/medicines", response_model=MedicineResponse, status_code=201, tags=["Medicines"])
async def add_medicine(body: MedicineCreate,
                        user=Depends(require_role("admin", "supervisor", "inventory_planner")),
                        db: AsyncSession = Depends(get_db)):
    return await create_medicine(db, body)


# ── Batches ───────────────────────────────────────────────────────────────────

@router.post("/inventory/batches", response_model=BatchResponse, status_code=201, tags=["Batches"])
async def receive(body: BatchCreate,
                  user=Depends(require_role("admin", "supervisor", "pharmacist", "inventory_planner")),
                  db: AsyncSession = Depends(get_db)):
    try:
        batch, _ = await receive_batch(db, body, user["sub"])
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return BatchResponse.model_validate(batch)


@router.post("/inventory/deduct", tags=["Stock"])
async def deduct(body: StockDeductRequest,
                  user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        new_total = await deduct_stock(db, body.medicine_id, body.outlet_id,
                                        body.quantity, body.reference_id, user["sub"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"deducted": body.quantity, "remaining_stock": new_total}


@router.post("/inventory/adjust", tags=["Stock"])
async def adjust(body: AdjustRequest,
                  user=Depends(require_role("admin", "supervisor")),
                  db: AsyncSession = Depends(get_db)):
    try:
        batch, old = await adjust_stock(db, body.batch_id, body.new_quantity, body.reason, user["sub"])
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"batch_id": str(batch.id), "before": old, "after": batch.quantity}


# ── Stock levels ──────────────────────────────────────────────────────────────

@router.get("/inventory/stock/{outlet_id}", response_model=List[StockLevelResponse], tags=["Stock"])
async def outlet_stock(outlet_id: str, user=Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    today = date.today()
    rows = await db.execute(
        select(Medicine.id, Medicine.name, Medicine.reorder_level,
               InventoryBatch.outlet_id,
               func.sum(InventoryBatch.quantity).label("total_stock"))
        .join(InventoryBatch, Medicine.id == InventoryBatch.medicine_id)
        .where(InventoryBatch.outlet_id == outlet_id,
               InventoryBatch.expiry_date > today,
               InventoryBatch.is_quarantined == False)
        .group_by(Medicine.id, Medicine.name, Medicine.reorder_level, InventoryBatch.outlet_id)
    )
    return [StockLevelResponse(medicine_id=r.id, name=r.name, outlet_id=r.outlet_id,
                                total_stock=r.total_stock or 0, reorder_level=r.reorder_level,
                                is_low_stock=(r.total_stock or 0) <= r.reorder_level)
            for r in rows.all()]


@router.get("/inventory/alerts/low-stock", tags=["Alerts"])
async def low_stock(outlet_id: Optional[str] = None,
                    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    today = date.today()
    q = (select(Medicine.id, Medicine.name, Medicine.reorder_level,
                InventoryBatch.outlet_id,
                func.sum(InventoryBatch.quantity).label("total_stock"))
         .join(InventoryBatch, Medicine.id == InventoryBatch.medicine_id)
         .where(InventoryBatch.expiry_date > today, InventoryBatch.is_quarantined == False))
    if outlet_id:
        q = q.where(InventoryBatch.outlet_id == outlet_id)
    q = (q.group_by(Medicine.id, Medicine.name, Medicine.reorder_level, InventoryBatch.outlet_id)
          .having(func.sum(InventoryBatch.quantity) <= Medicine.reorder_level))
    rows = await db.execute(q)
    return {
        "low_stock_items": [
            {
                "medicine_id": str(r.id), "name": r.name,
                "store_id": r.outlet_id, "outlet_id": r.outlet_id,
                "total_stock": r.total_stock, "reorder_level": r.reorder_level,
                "suggested_order_qty": max(0, r.reorder_level * 2 - r.total_stock),
            }
            for r in rows.all()
        ]
    }


@router.get("/inventory/alerts/expiring", tags=["Alerts"])
async def expiry_alerts(days: int = 30, outlet_id: Optional[str] = None,
                         user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    alerts = await get_expiry_alerts(db, days, outlet_id)
    return [{"id": str(b.id), "medicine_id": str(b.medicine_id), "batch_number": b.batch_number,
             "outlet_id": b.outlet_id, "quantity": b.quantity, "expiry_date": b.expiry_date.isoformat(),
             "days_to_expiry": d, "severity": s}
            for b, d, s in alerts]


@router.get("/inventory/ledger/{medicine_id}", response_model=List[LedgerResponse], tags=["Ledger"])
async def ledger(
    medicine_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(StockLedger).where(StockLedger.medicine_id == medicine_id)

    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    data_q = base_q.order_by(StockLedger.timestamp.desc()).offset(offset).limit(page_size)
    result = await db.execute(data_q)
    entries = [LedgerResponse.model_validate(e) for e in result.scalars().all()]

    return entries


# ── Stock Transfer ────────────────────────────────────────────────────────────

@router.post("/inventory/transfer", tags=["Stock"])
async def transfer_stock(
    body: StockTransferRequest,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    """
    Transfer stock between outlets (e.g. warehouse → store).
    Deducts from source outlet and creates a new batch at destination.
    """
    medicine_id = body.medicine_id
    from_outlet = body.from_outlet_id
    to_outlet = body.to_outlet_id
    qty = body.quantity

    if from_outlet == to_outlet:
        raise HTTPException(status_code=400, detail="Source and destination outlets must differ")

    try:
        new_source_total = await deduct_stock(
            db, medicine_id, from_outlet, qty,
            reference_id=f"TRANSFER-TO-{to_outlet}",
            user_id=user["sub"],
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Create batch at destination with earliest expiry from source (FEFO)
    from datetime import date, timedelta
    today = date.today()
    src_batch_result = await db.execute(
        select(InventoryBatch)
        .where(
            InventoryBatch.medicine_id == medicine_id,
            InventoryBatch.outlet_id == from_outlet,
            InventoryBatch.expiry_date > today,
            InventoryBatch.is_quarantined == False,
        )
        .order_by(InventoryBatch.expiry_date.asc())
        .limit(1)
    )
    src_batch = src_batch_result.scalar_one_or_none()
    expiry = src_batch.expiry_date if src_batch else today + timedelta(days=365)

    from app.schemas import BatchCreate
    import uuid as _uuid
    dest_batch_data = BatchCreate(
        medicine_id=medicine_id,
        batch_number=f"TRF-{str(_uuid.uuid4())[:8].upper()}",
        outlet_id=to_outlet,
        quantity=qty,
        expiry_date=expiry,
    )
    dest_batch, _ = await receive_batch(db, dest_batch_data, user["sub"])

    return {
        "message": "Stock transferred successfully",
        "medicine_id": medicine_id,
        "from_outlet_id": from_outlet,
        "to_outlet_id": to_outlet,
        "quantity_transferred": qty,
        "source_remaining_stock": new_source_total,
        "destination_batch_id": str(dest_batch.id),
    }


# ── Quarantine Management ─────────────────────────────────────────────────────

@router.post("/inventory/batches/{batch_id}/quarantine", tags=["Batches"])
async def quarantine_batch(
    batch_id: str,
    body: QuarantineRequest = QuarantineRequest(),
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    """Quarantine a batch — removes it from available stock calculations."""
    result = await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.is_quarantined:
        raise HTTPException(status_code=400, detail="Batch is already quarantined")
    batch.is_quarantined = True
    await db.commit()
    return {
        "message": "Batch quarantined",
        "batch_id": batch_id,
        "reason": body.reason,
    }


@router.post("/inventory/batches/{batch_id}/release", tags=["Batches"])
async def release_batch(
    batch_id: str,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    """Release a quarantined batch back into available stock."""
    result = await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if not batch.is_quarantined:
        raise HTTPException(status_code=400, detail="Batch is not quarantined")
    batch.is_quarantined = False
    await db.commit()
    return {"message": "Batch released from quarantine", "batch_id": batch_id}

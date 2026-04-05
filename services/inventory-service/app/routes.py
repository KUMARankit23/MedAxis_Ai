"""Inventory Service — FastAPI routes."""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models import Medicine, InventoryBatch, StockLedger
from app.schemas import (MedicineCreate, MedicineResponse, BatchCreate, BatchResponse,
                          StockDeductRequest, AdjustRequest, StockLevelResponse,
                          ExpiryAlertResponse, LedgerResponse)
from app.service import (create_medicine, list_medicines, receive_batch,
                          deduct_stock, adjust_stock, get_expiry_alerts, get_total_stock)
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

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

@router.get("/inventory/medicines", response_model=List[MedicineResponse], tags=["Medicines"])
async def list_meds(category: Optional[str] = None,
                    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await list_medicines(db, category)


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
    return [{"medicine_id": str(r.id), "name": r.name, "outlet_id": r.outlet_id,
             "total_stock": r.total_stock, "reorder_level": r.reorder_level}
            for r in rows.all()]


@router.get("/inventory/alerts/expiring", tags=["Alerts"])
async def expiry_alerts(days: int = 30, outlet_id: Optional[str] = None,
                         user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    alerts = await get_expiry_alerts(db, days, outlet_id)
    return [{"id": str(b.id), "medicine_id": str(b.medicine_id), "batch_number": b.batch_number,
             "outlet_id": b.outlet_id, "quantity": b.quantity, "expiry_date": b.expiry_date.isoformat(),
             "days_to_expiry": d, "severity": s}
            for b, d, s in alerts]


@router.get("/inventory/ledger/{medicine_id}", response_model=List[LedgerResponse], tags=["Ledger"])
async def ledger(medicine_id: str,
                  user=Depends(require_role("admin", "supervisor")),
                  db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StockLedger).where(StockLedger.medicine_id == medicine_id)
        .order_by(StockLedger.timestamp.desc()).limit(100)
    )
    return [LedgerResponse.model_validate(e) for e in result.scalars().all()]

"""Inventory Service — business logic layer."""
from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Medicine, InventoryBatch, StockLedger, MedicineCategory
from app.schemas import MedicineCreate, BatchCreate


async def get_total_stock(db: AsyncSession, medicine_id, outlet_id: str) -> int:
    today = date.today()
    result = await db.execute(
        select(func.sum(InventoryBatch.quantity)).where(
            InventoryBatch.medicine_id == medicine_id,
            InventoryBatch.outlet_id == outlet_id,
            InventoryBatch.expiry_date > today,
            InventoryBatch.is_quarantined == False,
        )
    )
    return result.scalar() or 0


async def _record_ledger(db, medicine_id, batch_id, outlet_id, txn_type,
                          qty_change, qty_after, ref_id=None, user_id=None, notes=None):
    db.add(StockLedger(
        medicine_id=medicine_id, batch_id=batch_id, outlet_id=outlet_id,
        transaction_type=txn_type, quantity_change=qty_change, quantity_after=qty_after,
        reference_id=ref_id, performed_by=user_id, notes=notes,
    ))


async def create_medicine(db: AsyncSession, data: MedicineCreate) -> Medicine:
    med = Medicine(**data.model_dump())
    db.add(med)
    await db.commit()
    await db.refresh(med)
    return med


async def list_medicines(db: AsyncSession, category: Optional[str] = None):
    q = select(Medicine).where(Medicine.is_active == True)
    if category:
        q = q.where(Medicine.category == category)
    result = await db.execute(q)
    return result.scalars().all()


async def receive_batch(db: AsyncSession, data: BatchCreate, user_id: str) -> InventoryBatch:
    result = await db.execute(select(Medicine).where(Medicine.id == data.medicine_id))
    med = result.scalar_one_or_none()
    if not med:
        raise LookupError("Medicine not found")

    batch = InventoryBatch(**data.model_dump())
    db.add(batch)
    await db.flush()

    total_after = await get_total_stock(db, data.medicine_id, data.outlet_id) + data.quantity
    await _record_ledger(db, data.medicine_id, batch.id, data.outlet_id,
                          "RECEIVE", data.quantity, total_after, user_id=user_id)
    await db.commit()
    await db.refresh(batch)
    return batch, total_after


async def deduct_stock(db: AsyncSession, medicine_id, outlet_id: str,
                        qty_needed: int, reference_id: str, user_id: str):
    """FEFO deduction with SELECT FOR UPDATE to prevent race conditions."""
    today = date.today()
    q = (select(InventoryBatch)
         .where(InventoryBatch.medicine_id == medicine_id,
                InventoryBatch.outlet_id == outlet_id,
                InventoryBatch.expiry_date > today,
                InventoryBatch.is_quarantined == False,
                InventoryBatch.quantity > 0)
         .order_by(InventoryBatch.expiry_date.asc())
         .with_for_update())

    result = await db.execute(q)
    batches = result.scalars().all()

    total_available = sum(b.quantity for b in batches)
    if total_available < qty_needed:
        raise ValueError(f"Insufficient stock: available={total_available}, requested={qty_needed}")

    remaining = qty_needed
    running = total_available
    for batch in batches:
        if remaining <= 0:
            break
        deduct = min(batch.quantity, remaining)
        batch.quantity -= deduct
        remaining -= deduct
        running -= deduct
        await _record_ledger(db, medicine_id, batch.id, outlet_id,
                              "SALE", -deduct, running, ref_id=reference_id, user_id=user_id)

    await db.commit()
    new_total = await get_total_stock(db, medicine_id, outlet_id)
    return new_total


async def adjust_stock(db: AsyncSession, batch_id, new_qty: int, reason: str, user_id: str):
    result = await db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise LookupError("Batch not found")
    if new_qty < 0:
        raise ValueError("Quantity cannot be negative")

    old_qty = batch.quantity
    batch.quantity = new_qty
    await _record_ledger(db, batch.medicine_id, batch.id, batch.outlet_id,
                          "ADJUSTMENT", new_qty - old_qty, new_qty,
                          user_id=user_id, notes=reason)
    await db.commit()
    return batch, old_qty


async def get_expiry_alerts(db: AsyncSession, days: int = 30, outlet_id: Optional[str] = None):
    today = date.today()
    cutoff = today + timedelta(days=days)
    q = (select(InventoryBatch)
         .where(InventoryBatch.expiry_date <= cutoff,
                InventoryBatch.expiry_date >= today,
                InventoryBatch.quantity > 0)
         .order_by(InventoryBatch.expiry_date.asc()))
    if outlet_id:
        q = q.where(InventoryBatch.outlet_id == outlet_id)
    result = await db.execute(q)
    batches = result.scalars().all()

    def severity(exp):
        d = (exp - today).days
        return "HIGH" if d <= 7 else ("MEDIUM" if d <= 15 else "LOW")

    return [(b, (b.expiry_date - today).days, severity(b.expiry_date)) for b in batches]

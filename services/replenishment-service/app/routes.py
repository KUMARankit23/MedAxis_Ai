"""Replenishment Service — FastAPI routes."""
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timezone
from app.database import get_db
from app.models import ReplenishmentOrder, OrderStatus, POCounter
from app.schemas import OrderCreate, ApproveRequest, CancelRequest, OrderResponse
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt
import httpx
import os

router = APIRouter()

INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8002")


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
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"Required roles: {list(roles)}")
        return user
    return dep


async def _generate_po_number(db: AsyncSession) -> str:
    """Generate a PO number in the format PO-{YYYYMMDD}-{seq:04d}."""
    from datetime import date
    date_key = date.today().strftime("%Y%m%d")

    result = await db.execute(select(POCounter).where(POCounter.date_key == date_key))
    counter = result.scalar_one_or_none()

    if counter is None:
        counter = POCounter(date_key=date_key, last_seq=1)
        db.add(counter)
    else:
        counter.last_seq += 1

    await db.flush()  # ensure last_seq is written before we read it
    return f"PO-{date_key}-{counter.last_seq:04d}"


@router.get("/replenishment/orders", tags=["Replenishment"])
async def list_orders(
    status: Optional[str] = None,
    outlet_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Count query
    count_q = select(func.count(ReplenishmentOrder.id))
    if status:
        count_q = count_q.where(ReplenishmentOrder.status == status.upper())
    if outlet_id:
        count_q = count_q.where(ReplenishmentOrder.outlet_id == outlet_id)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Data query
    q = select(ReplenishmentOrder).order_by(ReplenishmentOrder.created_at.desc())
    if status:
        q = q.where(ReplenishmentOrder.status == status.upper())
    if outlet_id:
        q = q.where(ReplenishmentOrder.outlet_id == outlet_id)

    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)
    result = await db.execute(q)
    orders = [OrderResponse.model_validate(o) for o in result.scalars().all()]

    return {
        "orders": [o.model_dump() for o in orders],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/replenishment/orders", response_model=OrderResponse, status_code=201, tags=["Replenishment"])
async def create_order(
    body: OrderCreate,
    user=Depends(require_role("admin", "supervisor", "pharmacist", "inventory_planner")),
    db: AsyncSession = Depends(get_db),
):
    po_number = await _generate_po_number(db)
    order = ReplenishmentOrder(
        **body.model_dump(),
        po_number=po_number,
        trigger_reason="MANUAL",
        created_by=user["sub"],
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.post("/replenishment/orders/{order_id}/approve", response_model=OrderResponse, tags=["Replenishment"])
async def approve(
    order_id: str,
    body: ApproveRequest,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.suggested:
        raise HTTPException(status_code=400, detail=f"Cannot approve order in status: {order.status.value}")
    order.status = OrderStatus.approved
    order.approved_quantity = body.approved_quantity or order.suggested_quantity
    order.approved_by = user["sub"]
    if body.notes:
        order.notes = body.notes
    await db.commit()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.post("/replenishment/orders/{order_id}/cancel", response_model=OrderResponse, tags=["Replenishment"])
async def cancel_order(
    order_id: str,
    body: CancelRequest = CancelRequest(),
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a replenishment order (admin/supervisor only)."""
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == OrderStatus.cancelled:
        raise HTTPException(status_code=400, detail="Order is already cancelled")
    if order.status == OrderStatus.received:
        raise HTTPException(status_code=400, detail="Cannot cancel a received order")

    order.status = OrderStatus.cancelled
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancel_reason = body.cancel_reason or "Cancelled by user"
    await db.commit()
    await db.refresh(order)
    return OrderResponse.model_validate(order)


@router.post("/replenishment/orders/{order_id}/mark-ordered", tags=["Replenishment"])
async def mark_ordered(
    order_id: str,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.approved:
        raise HTTPException(status_code=400, detail=f"Cannot mark-ordered from status: {order.status.value}")
    order.status = OrderStatus.ordered
    await db.commit()
    return {"message": "Order marked as ordered", "order_id": order_id}


@router.post("/replenishment/orders/{order_id}/receive", tags=["Replenishment"])
async def receive(
    order_id: str,
    request: Request,
    body: dict = {},
    user=Depends(require_role("admin", "supervisor", "pharmacist")),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark order as received and automatically create an inventory batch
    via the inventory service so stock is immediately updated.
    """
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.ordered:
        raise HTTPException(status_code=400, detail=f"Cannot receive order in status: {order.status.value}")

    # Auto-create inventory batch
    from datetime import date, timedelta
    token = request.headers.get("Authorization", "").split(" ", 1)[-1]
    batch_number = body.get("batch_number", f"PO-{str(order.id)[:8].upper()}")
    expiry_date = body.get("expiry_date", (date.today() + timedelta(days=365)).isoformat())
    qty = order.approved_quantity or order.suggested_quantity

    batch_created = False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{INVENTORY_URL}/inventory/batches",
                json={
                    "medicine_id": order.medicine_id,
                    "batch_number": batch_number,
                    "outlet_id": order.outlet_id,
                    "quantity": qty,
                    "expiry_date": expiry_date,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            batch_created = resp.status_code == 201
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Auto batch creation failed: {e}")

    order.status = OrderStatus.received
    await db.commit()

    return {
        "message": "Order received",
        "order_id": order_id,
        "batch_created": batch_created,
        "quantity_received": qty,
        "note": "Stock batch created automatically." if batch_created else "Batch creation failed — add stock manually via /inventory/batches.",
    }

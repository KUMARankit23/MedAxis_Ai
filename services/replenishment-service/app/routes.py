from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.database import get_db
from app.models import ReplenishmentOrder, OrderStatus
from app.schemas import OrderCreate, ApproveRequest, OrderResponse
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

router = APIRouter()

def get_current_user(request: Request):
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "): raise HTTPException(401,"Missing token")
    try:
        p = pyjwt.decode(auth.split(" ",1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if p.get("type") != "access": raise HTTPException(401,"Invalid token type")
        return p
    except: raise HTTPException(401,"Invalid or expired token")

def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user.get("role") not in roles: raise HTTPException(403,f"Required: {list(roles)}")
        return user
    return dep

@router.get("/replenishment/orders", response_model=List[OrderResponse], tags=["Replenishment"])
async def list_orders(status: Optional[str]=None, outlet_id: Optional[str]=None,
                       user=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    q = select(ReplenishmentOrder).order_by(ReplenishmentOrder.created_at.desc()).limit(100)
    if status: q = q.where(ReplenishmentOrder.status == status.upper())
    if outlet_id: q = q.where(ReplenishmentOrder.outlet_id == outlet_id)
    result = await db.execute(q)
    return [OrderResponse.model_validate(o) for o in result.scalars().all()]

@router.post("/replenishment/orders", response_model=OrderResponse, status_code=201, tags=["Replenishment"])
async def create_order(body: OrderCreate, user=Depends(require_role("admin","supervisor","pharmacist","inventory_planner")), db: AsyncSession=Depends(get_db)):
    order = ReplenishmentOrder(**body.model_dump(), trigger_reason="MANUAL", created_by=user["sub"])
    db.add(order); await db.commit(); await db.refresh(order)
    return OrderResponse.model_validate(order)

@router.post("/replenishment/orders/{order_id}/approve", response_model=OrderResponse, tags=["Replenishment"])
async def approve(order_id: str, body: ApproveRequest, user=Depends(require_role("admin","supervisor")), db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order: raise HTTPException(404,"Order not found")
    if order.status != OrderStatus.suggested: raise HTTPException(400,f"Cannot approve: {order.status.value}")
    order.status = OrderStatus.approved
    order.approved_quantity = body.approved_quantity or order.suggested_quantity
    order.approved_by = user["sub"]
    if body.notes: order.notes = body.notes
    await db.commit(); await db.refresh(order)
    return OrderResponse.model_validate(order)

@router.post("/replenishment/orders/{order_id}/mark-ordered", tags=["Replenishment"])
async def mark_ordered(order_id: str, user=Depends(require_role("admin","supervisor")), db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order: raise HTTPException(404,"Order not found")
    order.status = OrderStatus.ordered; await db.commit()
    return {"message": "Marked as ordered"}

@router.post("/replenishment/orders/{order_id}/receive", tags=["Replenishment"])
async def receive(order_id: str, user=Depends(require_role("admin","supervisor","pharmacist")), db: AsyncSession=Depends(get_db)):
    result = await db.execute(select(ReplenishmentOrder).where(ReplenishmentOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order: raise HTTPException(404,"Order not found")
    order.status = OrderStatus.received; await db.commit()
    return {"message": "Order received. Add stock via /inventory/batches."}

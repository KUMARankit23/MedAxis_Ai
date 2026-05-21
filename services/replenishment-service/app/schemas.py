from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models import OrderStatus

class OrderCreate(BaseModel):
    medicine_id: str; outlet_id: str; suggested_quantity: int
    medicine_name: Optional[str]=None; current_stock: Optional[int]=None; notes: Optional[str]=None

class ApproveRequest(BaseModel):
    approved_quantity: Optional[int]=None; notes: Optional[str]=None

class CancelRequest(BaseModel):
    cancel_reason: Optional[str] = None

class OrderResponse(BaseModel):
    id: UUID; po_number: Optional[str]; medicine_id: str; medicine_name: Optional[str]
    outlet_id: str; suggested_quantity: int; approved_quantity: Optional[int]
    trigger_reason: str; current_stock: Optional[int]; ai_confidence: Optional[float]
    ai_explanation: Optional[str]; status: OrderStatus; created_by: Optional[str]
    created_at: datetime; cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    model_config = {"from_attributes": True}


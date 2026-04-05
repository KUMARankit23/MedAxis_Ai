from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models import InvoiceStatus, PaymentMethod

class InvoiceItemCreate(BaseModel):
    medicine_id: str; medicine_name: str; quantity: int
    unit_price: float; discount_pct: float = 0.0
    category: str = "OTC"; is_prescription_item: bool = False

class InvoiceCreate(BaseModel):
    outlet_id: str; items: List[InvoiceItemCreate]
    patient_name: Optional[str] = None; prescription_id: Optional[UUID] = None
    payment_method: PaymentMethod = PaymentMethod.cash
    discount: float = 0.0; notes: Optional[str] = None

class InvoiceItemResponse(BaseModel):
    id: UUID; medicine_id: str; medicine_name: str; quantity: int
    unit_price: float; discount_pct: float; gst_rate: float; line_total: float
    class Config: from_attributes = True

class InvoiceResponse(BaseModel):
    id: UUID; invoice_number: str; outlet_id: str
    patient_name: Optional[str]; subtotal: float; discount: float
    tax: float; total: float; payment_method: PaymentMethod
    status: InvoiceStatus; created_at: datetime
    items: List[InvoiceItemResponse]
    class Config: from_attributes = True

class PrescriptionCreate(BaseModel):
    patient_name: str; doctor_name: str; prescription_date: datetime
    outlet_id: str; patient_phone: Optional[str] = None
    doctor_license: Optional[str] = None; notes: Optional[str] = None

class PrescriptionResponse(BaseModel):
    id: UUID; patient_name: str; doctor_name: str
    prescription_date: datetime; outlet_id: str
    class Config: from_attributes = True

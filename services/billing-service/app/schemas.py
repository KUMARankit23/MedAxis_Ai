from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models import InvoiceStatus, PaymentMethod

class InvoiceItemCreate(BaseModel):
    medicine_id: str; medicine_name: str; quantity: int
    unit_price: float; discount_pct: float = 0.0
    category: str = "OTC"; is_prescription_item: bool = False

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, v):
        if v < 0:
            raise ValueError("unit_price must be >= 0")
        return v

    @field_validator("discount_pct")
    @classmethod
    def discount_pct_range(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("discount_pct must be between 0 and 100")
        return v

class InvoiceCreate(BaseModel):
    outlet_id: str; items: List[InvoiceItemCreate]
    patient_name: Optional[str] = None; prescription_id: Optional[UUID] = None
    payment_method: PaymentMethod = PaymentMethod.cash
    discount: float = 0.0; notes: Optional[str] = None

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v):
        if not v:
            raise ValueError("items list must not be empty")
        return v

class InvoiceItemResponse(BaseModel):
    id: UUID; medicine_id: str; medicine_name: str; quantity: int
    unit_price: float; discount_pct: float; gst_rate: float; line_total: float
    model_config = {"from_attributes": True}

class InvoiceResponse(BaseModel):
    id: UUID; invoice_number: str; outlet_id: str
    patient_name: Optional[str]; subtotal: float; discount: float
    tax: float; total: float; payment_method: PaymentMethod
    status: InvoiceStatus; created_at: datetime
    items: List[InvoiceItemResponse]
    model_config = {"from_attributes": True}

class PrescriptionCreate(BaseModel):
    patient_name: str; doctor_name: str; prescription_date: datetime
    outlet_id: str; patient_phone: Optional[str] = None
    doctor_license: Optional[str] = None; notes: Optional[str] = None

class PrescriptionResponse(BaseModel):
    id: UUID; patient_name: str; doctor_name: str
    prescription_date: datetime; outlet_id: str
    model_config = {"from_attributes": True}


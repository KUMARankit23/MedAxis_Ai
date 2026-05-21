"""Inventory Service — Pydantic schemas."""
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from app.models import MedicineCategory


class MedicineCreate(BaseModel):
    name: str; category: MedicineCategory; unit_price: float
    generic_name: Optional[str] = None; manufacturer: Optional[str] = None
    unit: str = "units"; reorder_level: int = 20; reorder_quantity: int = 100

    @field_validator("unit_price")
    @classmethod
    def unit_price_positive(cls, v):
        if v <= 0:
            raise ValueError("unit_price must be greater than 0")
        return v

    @field_validator("reorder_level")
    @classmethod
    def reorder_level_non_negative(cls, v):
        if v < 0:
            raise ValueError("reorder_level must be >= 0")
        return v

    @field_validator("reorder_quantity")
    @classmethod
    def reorder_quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("reorder_quantity must be greater than 0")
        return v

class MedicineResponse(BaseModel):
    id: UUID; name: str; generic_name: Optional[str]; manufacturer: Optional[str]
    category: MedicineCategory; unit: str; unit_price: float
    reorder_level: int; reorder_quantity: int
    model_config = {"from_attributes": True}

class BatchCreate(BaseModel):
    medicine_id: UUID; batch_number: str; outlet_id: str
    quantity: int; expiry_date: date; purchase_price: Optional[float] = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v):
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("expiry_date")
    @classmethod
    def expiry_not_in_past(cls, v):
        if v < date.today():
            raise ValueError("expiry_date must be today or in the future")
        return v

class BatchResponse(BaseModel):
    id: UUID; medicine_id: UUID; batch_number: str; outlet_id: str
    quantity: int; expiry_date: date; is_quarantined: bool
    model_config = {"from_attributes": True}

class StockDeductRequest(BaseModel):
    medicine_id: UUID; outlet_id: str; quantity: int; reference_id: str

class AdjustRequest(BaseModel):
    batch_id: UUID; new_quantity: int; reason: str

class StockLevelResponse(BaseModel):
    medicine_id: UUID; name: str; outlet_id: str
    total_stock: int; reorder_level: int; is_low_stock: bool

class ExpiryAlertResponse(BaseModel):
    id: UUID; medicine_id: UUID; batch_number: str; outlet_id: str
    quantity: int; expiry_date: date; days_to_expiry: int; severity: str
    model_config = {"from_attributes": True}

class LedgerResponse(BaseModel):
    id: UUID; medicine_id: UUID; outlet_id: str; transaction_type: str
    quantity_change: int; quantity_after: int; reference_id: Optional[str]
    performed_by: Optional[str]; timestamp: datetime
    model_config = {"from_attributes": True}


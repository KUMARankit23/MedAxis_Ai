"""
Inventory Service — Database models.
Owns: medicines, inventory_batches, stock_ledger tables.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean,
    DateTime, Date, Text, ForeignKey, Enum, Index
)
from sqlalchemy.orm import declarative_base, relationship
from shared.compat import GUID
import uuid
import enum

Base = declarative_base()


class MedicineCategory(str, enum.Enum):
    otc = "OTC"
    prescription = "PRESCRIPTION"
    controlled = "CONTROLLED"


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    generic_name = Column(String(200), nullable=True)
    manufacturer = Column(String(200), nullable=True)
    category = Column(Enum(MedicineCategory), nullable=False, default=MedicineCategory.otc)
    unit = Column(String(50), default="units")
    unit_price = Column(Float, nullable=False)
    reorder_level = Column(Integer, default=20)
    reorder_quantity = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    batches = relationship("InventoryBatch", back_populates="medicine", lazy="dynamic")
    ledger_entries = relationship("StockLedger", back_populates="medicine", lazy="dynamic")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "generic_name": self.generic_name,
            "manufacturer": self.manufacturer,
            "category": self.category.value,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "reorder_level": self.reorder_level,
            "reorder_quantity": self.reorder_quantity,
        }


class InventoryBatch(Base):
    """Tracks individual stock batches with expiry (FEFO compliance)."""
    __tablename__ = "inventory_batches"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    medicine_id = Column(GUID(), ForeignKey("medicines.id"), nullable=False)
    batch_number = Column(String(100), nullable=False)
    store_id = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    expiry_date = Column(Date, nullable=False)
    purchase_price = Column(Float, nullable=True)
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_quarantined = Column(Boolean, default=False)

    medicine = relationship("Medicine", back_populates="batches")

    def to_dict(self):
        return {
            "id": str(self.id),
            "medicine_id": str(self.medicine_id),
            "batch_number": self.batch_number,
            "store_id": self.store_id,
            "quantity": self.quantity,
            "expiry_date": self.expiry_date.isoformat(),
            "purchase_price": self.purchase_price,
            "is_quarantined": self.is_quarantined,
        }


class StockLedger(Base):
    """Immutable audit trail for every stock movement."""
    __tablename__ = "stock_ledger"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    medicine_id = Column(GUID(), ForeignKey("medicines.id"), nullable=False)
    batch_id = Column(GUID(), ForeignKey("inventory_batches.id"), nullable=True)
    store_id = Column(String(50), nullable=False)
    transaction_type = Column(String(50), nullable=False)
    quantity_change = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reference_id = Column(String(200), nullable=True)
    performed_by = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="ledger_entries")

    def to_dict(self):
        return {
            "id": str(self.id),
            "medicine_id": str(self.medicine_id),
            "batch_id": str(self.batch_id) if self.batch_id else None,
            "store_id": self.store_id,
            "transaction_type": self.transaction_type,
            "quantity_change": self.quantity_change,
            "quantity_after": self.quantity_after,
            "reference_id": self.reference_id,
            "performed_by": self.performed_by,
            "timestamp": self.timestamp.isoformat(),
        }

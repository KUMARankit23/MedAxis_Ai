"""Inventory Service — ORM models."""
import uuid, enum
from datetime import datetime, timezone
from sqlalchemy import (Column, String, Integer, Float, Boolean,
                        DateTime, Date, Text, ForeignKey, Enum, Index)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class MedicineCategory(str, enum.Enum):
    otc          = "OTC"
    prescription = "PRESCRIPTION"
    controlled   = "CONTROLLED"


class Medicine(Base):
    __tablename__ = "medicines"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name             = Column(String(200), nullable=False, index=True)
    generic_name     = Column(String(200))
    manufacturer     = Column(String(200))
    category         = Column(Enum(MedicineCategory), nullable=False, default=MedicineCategory.otc)
    unit             = Column(String(50), default="units")
    unit_price       = Column(Float, nullable=False)
    reorder_level    = Column(Integer, default=20)
    reorder_quantity = Column(Integer, default=100)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    batches       = relationship("InventoryBatch", back_populates="medicine", lazy="select")
    ledger_entries = relationship("StockLedger",   back_populates="medicine", lazy="select")


class InventoryBatch(Base):
    """Physical stock batch — FEFO (First Expiry First Out) compliance."""
    __tablename__ = "inventory_batches"
    __table_args__ = (
        Index("ix_batch_medicine_outlet", "medicine_id", "outlet_id"),
        Index("ix_batch_expiry", "expiry_date"),
    )
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id    = Column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    batch_number   = Column(String(100), nullable=False)
    outlet_id      = Column(String(50), nullable=False)
    quantity       = Column(Integer, nullable=False, default=0)
    expiry_date    = Column(Date, nullable=False)
    purchase_price = Column(Float)
    is_quarantined = Column(Boolean, default=False)
    received_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="batches")


class StockLedger(Base):
    """Immutable audit trail — append-only, never UPDATE or DELETE."""
    __tablename__ = "stock_ledger"
    __table_args__ = (
        Index("ix_ledger_medicine_outlet", "medicine_id", "outlet_id"),
        Index("ix_ledger_timestamp", "timestamp"),
    )
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id      = Column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    batch_id         = Column(UUID(as_uuid=True), ForeignKey("inventory_batches.id"))
    outlet_id        = Column(String(50), nullable=False)
    transaction_type = Column(String(50), nullable=False)  # RECEIVE, SALE, ADJUSTMENT, RETURN
    quantity_change  = Column(Integer, nullable=False)      # +in / -out
    quantity_after   = Column(Integer, nullable=False)      # running balance
    reference_id     = Column(String(200))                  # invoice_id, PO number
    performed_by     = Column(String(200))
    notes            = Column(Text)
    timestamp        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    medicine = relationship("Medicine", back_populates="ledger_entries")

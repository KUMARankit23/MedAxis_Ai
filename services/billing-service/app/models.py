"""Billing Service — ORM models."""
import uuid, enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class InvoiceStatus(str, enum.Enum):
    draft="DRAFT"; confirmed="CONFIRMED"; cancelled="CANCELLED"; refunded="REFUNDED"

class PaymentMethod(str, enum.Enum):
    cash="CASH"; card="CARD"; insurance="INSURANCE"; upi="UPI"

class Prescription(Base):
    __tablename__ = "prescriptions"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_name      = Column(String(200), nullable=False)
    patient_phone     = Column(String(20))
    doctor_name       = Column(String(200), nullable=False)
    doctor_license    = Column(String(100))
    prescription_date = Column(DateTime(timezone=True), nullable=False)
    notes             = Column(Text)
    outlet_id         = Column(String(50), nullable=False)
    created_by        = Column(String(200))
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    invoices = relationship("Invoice", back_populates="prescription")

class Invoice(Base):
    __tablename__ = "invoices"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number  = Column(String(50), unique=True, nullable=False, index=True)
    outlet_id       = Column(String(50), nullable=False, index=True)
    prescription_id = Column(UUID(as_uuid=True), ForeignKey("prescriptions.id"))
    patient_name    = Column(String(200))
    pharmacist_id   = Column(String(200), nullable=False)
    subtotal        = Column(Float, default=0.0)
    discount        = Column(Float, default=0.0)
    tax             = Column(Float, default=0.0)
    total           = Column(Float, default=0.0)
    payment_method  = Column(Enum(PaymentMethod), default=PaymentMethod.cash)
    status          = Column(Enum(InvoiceStatus), default=InvoiceStatus.draft, index=True)
    notes           = Column(Text)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    confirmed_at    = Column(DateTime(timezone=True))
    prescription = relationship("Prescription", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id           = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False)
    medicine_id          = Column(String(200), nullable=False)
    medicine_name        = Column(String(200), nullable=False)
    quantity             = Column(Integer, nullable=False)
    unit_price           = Column(Float, nullable=False)
    discount_pct         = Column(Float, default=0.0)
    gst_rate             = Column(Float, default=0.05)
    line_total           = Column(Float, nullable=False)
    is_prescription_item = Column(Boolean, default=False)
    invoice = relationship("Invoice", back_populates="items")

"""
Billing Service — Database models.
Owns: prescriptions, invoices, invoice_items tables.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
from shared.compat import GUID
import uuid
import enum

Base = declarative_base()


class InvoiceStatus(str, enum.Enum):
    draft = "DRAFT"
    confirmed = "CONFIRMED"
    cancelled = "CANCELLED"
    refunded = "REFUNDED"


class PaymentMethod(str, enum.Enum):
    cash = "CASH"
    card = "CARD"
    insurance = "INSURANCE"
    upi = "UPI"


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    patient_name = Column(String(200), nullable=False)
    patient_phone = Column(String(20), nullable=True)
    doctor_name = Column(String(200), nullable=False)
    doctor_license = Column(String(100), nullable=True)
    prescription_date = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)
    store_id = Column(String(50), nullable=False)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoices = relationship("Invoice", back_populates="prescription")

    def to_dict(self):
        return {
            "id": str(self.id),
            "patient_name": self.patient_name,
            "doctor_name": self.doctor_name,
            "doctor_license": self.doctor_license,
            "prescription_date": self.prescription_date.isoformat(),
            "store_id": self.store_id,
        }


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False)
    store_id = Column(String(50), nullable=False)
    prescription_id = Column(GUID(), ForeignKey("prescriptions.id"), nullable=True)
    patient_name = Column(String(200), nullable=True)
    pharmacist_id = Column(String(200), nullable=False)
    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.cash)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.draft)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime, nullable=True)

    prescription = relationship("Prescription", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "invoice_number": self.invoice_number,
            "store_id": self.store_id,
            "prescription_id": str(self.prescription_id) if self.prescription_id else None,
            "patient_name": self.patient_name,
            "subtotal": self.subtotal,
            "discount": self.discount,
            "tax": self.tax,
            "total": self.total,
            "payment_method": self.payment_method.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "items": [i.to_dict() for i in self.items],
        }


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(GUID(), ForeignKey("invoices.id"), nullable=False)
    medicine_id = Column(String(200), nullable=False)
    medicine_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    discount_pct = Column(Float, default=0.0)
    line_total = Column(Float, nullable=False)
    is_prescription_item = Column(Boolean, default=False)

    invoice = relationship("Invoice", back_populates="items")

    def to_dict(self):
        return {
            "id": str(self.id),
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "discount_pct": self.discount_pct,
            "line_total": self.line_total,
            "is_prescription_item": self.is_prescription_item,
        }

"""
Replenishment Service — Database models.
Owns: replenishment_orders table.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.orm import declarative_base
from shared.compat import GUID
import uuid
import enum

Base = declarative_base()


class OrderStatus(str, enum.Enum):
    suggested = "SUGGESTED"
    approved = "APPROVED"
    ordered = "ORDERED"
    received = "RECEIVED"
    cancelled = "CANCELLED"


class ReplenishmentOrder(Base):
    __tablename__ = "replenishment_orders"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    medicine_id = Column(String(200), nullable=False)
    medicine_name = Column(String(200), nullable=True)
    store_id = Column(String(50), nullable=False)
    suggested_quantity = Column(Integer, nullable=False)
    approved_quantity = Column(Integer, nullable=True)
    trigger_reason = Column(String(100), nullable=False)
    current_stock = Column(Integer, nullable=True)
    reorder_level = Column(Integer, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.suggested)
    created_by = Column(String(200), nullable=True)
    approved_by = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine_name,
            "store_id": self.store_id,
            "suggested_quantity": self.suggested_quantity,
            "approved_quantity": self.approved_quantity,
            "trigger_reason": self.trigger_reason,
            "current_stock": self.current_stock,
            "reorder_level": self.reorder_level,
            "ai_confidence": self.ai_confidence,
            "ai_explanation": self.ai_explanation,
            "status": self.status.value,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
        }

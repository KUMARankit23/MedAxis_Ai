import uuid, enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class OrderStatus(str, enum.Enum):
    suggested="SUGGESTED"; approved="APPROVED"; ordered="ORDERED"; received="RECEIVED"; cancelled="CANCELLED"

class ReplenishmentOrder(Base):
    __tablename__ = "replenishment_orders"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id       = Column(String(200), nullable=False)
    medicine_name     = Column(String(200))
    outlet_id         = Column(String(50), nullable=False)
    suggested_quantity = Column(Integer, nullable=False)
    approved_quantity  = Column(Integer)
    trigger_reason    = Column(String(100), nullable=False)  # LOW_STOCK | FORECAST | MANUAL
    current_stock     = Column(Integer)
    reorder_level     = Column(Integer)
    ai_confidence     = Column(Float)
    ai_explanation    = Column(Text)
    status            = Column(Enum(OrderStatus), default=OrderStatus.suggested, index=True)
    created_by        = Column(String(200))
    approved_by       = Column(String(200))
    notes             = Column(Text)
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

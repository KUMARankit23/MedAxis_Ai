import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class ForecastResult(Base):
    __tablename__ = "forecast_results"
    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medicine_id             = Column(String(200), nullable=False, index=True)
    medicine_name           = Column(String(200))
    outlet_id               = Column(String(50), nullable=False)
    forecast_date           = Column(Date, nullable=False)
    predicted_demand        = Column(Float, nullable=False)
    confidence_score        = Column(Float)
    model_used              = Column(String(100), default="linear_regression")
    explanation             = Column(Text)
    triggered_replenishment = Column(Boolean, default=False)
    created_at              = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_type   = Column(String(100), nullable=False)
    medicine_id    = Column(String(200), index=True)
    outlet_id      = Column(String(50))
    severity       = Column(String(20), default="MEDIUM")
    description    = Column(Text, nullable=False)
    detected_value = Column(Float)
    expected_range = Column(String(100))
    is_resolved    = Column(Boolean, default=False, index=True)
    resolution_notes = Column(Text)
    detected_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at    = Column(DateTime(timezone=True))

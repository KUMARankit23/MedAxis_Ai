"""
AI Insights Service — Database models.
Owns: forecast_results, anomaly_logs tables.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, Date
from sqlalchemy.orm import declarative_base
from shared.compat import GUID
import uuid

Base = declarative_base()


class ForecastResult(Base):
    __tablename__ = "forecast_results"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    medicine_id = Column(String(200), nullable=False)
    medicine_name = Column(String(200), nullable=True)
    store_id = Column(String(50), nullable=False)
    forecast_date = Column(Date, nullable=False)
    predicted_demand = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=True)
    model_used = Column(String(100), default="linear_regression")
    explanation = Column(Text, nullable=True)
    triggered_replenishment = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "medicine_id": self.medicine_id,
            "medicine_name": self.medicine_name,
            "store_id": self.store_id,
            "forecast_date": self.forecast_date.isoformat(),
            "predicted_demand": round(self.predicted_demand, 2),
            "confidence_score": self.confidence_score,
            "model_used": self.model_used,
            "explanation": self.explanation,
            "triggered_replenishment": self.triggered_replenishment,
        }


class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    anomaly_type = Column(String(100), nullable=False)
    medicine_id = Column(String(200), nullable=True)
    store_id = Column(String(50), nullable=True)
    severity = Column(String(20), default="MEDIUM")
    description = Column(Text, nullable=False)
    detected_value = Column(Float, nullable=True)
    expected_range = Column(String(100), nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "anomaly_type": self.anomaly_type,
            "medicine_id": self.medicine_id,
            "store_id": self.store_id,
            "severity": self.severity,
            "description": self.description,
            "detected_value": self.detected_value,
            "expected_range": self.expected_range,
            "is_resolved": self.is_resolved,
            "detected_at": self.detected_at.isoformat(),
        }

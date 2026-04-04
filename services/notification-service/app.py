"""
Notification Service — Entry point.
Listens to events and dispatches alerts (logs to console, simulates email/SMS).
Port: 8007
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import logging
import threading
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid

from shared.db_utils import make_engine
from shared.event_bus import subscribe_and_handle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Notification Model ───────────────────────────────────────────────────────

Base = declarative_base()

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_type = Column(String(100), nullable=False)
    channel = Column(String(50), default="LOG")   # LOG, EMAIL, SMS (simulated)
    recipient = Column(String(200), nullable=True)
    subject = Column(String(300), nullable=True)
    message = Column(Text, nullable=False)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "type": self.notification_type,
            "subject": self.subject,
            "message": self.message,
            "is_sent": self.is_sent,
            "created_at": self.created_at.isoformat(),
        }

engine = make_engine("medaxis_notifications")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def send_notification(notif_type: str, subject: str, message: str, recipient: str = "ops-team"):
    """Simulate sending a notification (logs it + persists to DB)."""
    logger.warning(f"[NOTIFICATION] [{notif_type}] {subject}: {message}")
    db = SessionLocal()
    try:
        n = Notification(
            notification_type=notif_type,
            recipient=recipient,
            subject=subject,
            message=message,
            is_sent=True,
        )
        db.add(n)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist notification: {e}")
    finally:
        db.close()


# ─── Event Handlers ──────────────────────────────────────────────────────────

def on_anomaly_detected(payload: dict):
    severity = payload.get("severity", "MEDIUM")
    medicine = payload.get("medicine_id", "unknown")
    store = payload.get("store_id", "unknown")
    desc = payload.get("description", "")
    send_notification(
        "ANOMALY_ALERT",
        f"[{severity}] Anomaly detected: {payload.get('anomaly_type')}",
        f"Medicine: {medicine} | Store: {store}\n{desc}",
    )


def on_low_stock(payload: dict):
    send_notification(
        "LOW_STOCK_ALERT",
        f"Low stock: {payload.get('medicine_name')} at {payload.get('store_id')}",
        f"Current stock: {payload.get('current_stock')} (reorder level: {payload.get('reorder_level')})",
    )


def on_replenishment_approved(payload: dict):
    send_notification(
        "REPLENISHMENT_APPROVED",
        f"Replenishment approved: {payload.get('medicine_name')}",
        f"Store: {payload.get('store_id')} | Quantity: {payload.get('quantity')}",
    )


def start_listeners():
    def listen_notifications():
        subscribe_and_handle("notifications", {
            "ANOMALY_DETECTED": on_anomaly_detected,
            "REPLENISHMENT_APPROVED": on_replenishment_approved,
        })
    def listen_inventory():
        subscribe_and_handle("inventory", {
            "LOW_STOCK_ALERT": on_low_stock,
        })
    threading.Thread(target=listen_notifications, daemon=True).start()
    threading.Thread(target=listen_inventory, daemon=True).start()


# ─── API ──────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"service": "notification-service", "status": "ok"})


@app.route("/notifications", methods=["GET"])
def list_notifications():
    db = SessionLocal()
    try:
        notifs = db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()
        return jsonify({"notifications": [n.to_dict() for n in notifs]})
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    start_listeners()
    app.run(host="0.0.0.0", port=8007, debug=False)

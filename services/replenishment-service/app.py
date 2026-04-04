"""
Replenishment Service — Entry point.
Handles: reorder detection, AI-driven suggestions, order lifecycle.
Listens to: LOW_STOCK_ALERT and FORECAST_TRIGGERED_REPLENISHMENT events.
Port: 8004
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import logging
import threading

from flask import Flask, request, jsonify, g

from database import init_db, SessionLocal
from models import ReplenishmentOrder, OrderStatus
from shared.auth_middleware import require_auth, require_role
from shared.audit_logger import log_action
from shared.event_bus import publish_event, subscribe_and_handle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ─── Event Handlers ──────────────────────────────────────────────────────────

def handle_low_stock_alert(payload: dict):
    """
    React to LOW_STOCK_ALERT from inventory service.
    Auto-creates a replenishment suggestion.
    """
    logger.info(f"[REPLENISHMENT] Low stock alert received: {payload}")
    db = SessionLocal()
    try:
        # Avoid duplicate suggestions
        existing = db.query(ReplenishmentOrder).filter(
            ReplenishmentOrder.medicine_id == payload["medicine_id"],
            ReplenishmentOrder.store_id == payload["store_id"],
            ReplenishmentOrder.status == OrderStatus.suggested,
        ).first()
        if existing:
            logger.info(f"[REPLENISHMENT] Suggestion already exists for {payload['medicine_id']}")
            return

        # Suggest 2x the reorder level as a safe quantity
        suggested_qty = payload.get("reorder_level", 100) * 2

        order = ReplenishmentOrder(
            medicine_id=payload["medicine_id"],
            medicine_name=payload.get("medicine_name"),
            store_id=payload["store_id"],
            suggested_quantity=suggested_qty,
            trigger_reason="LOW_STOCK",
            current_stock=payload.get("current_stock"),
            reorder_level=payload.get("reorder_level"),
            created_by="system-auto",
        )
        db.add(order)
        db.commit()
        logger.info(f"[REPLENISHMENT] Auto-created suggestion: {suggested_qty} units of {payload.get('medicine_name')}")
    finally:
        db.close()


def handle_forecast_replenishment(payload: dict):
    """
    React to FORECAST_TRIGGERED_REPLENISHMENT from AI service.
    Creates an AI-backed replenishment suggestion with explanation.
    """
    logger.info(f"[REPLENISHMENT] Forecast-triggered replenishment: {payload}")
    db = SessionLocal()
    try:
        existing = db.query(ReplenishmentOrder).filter(
            ReplenishmentOrder.medicine_id == payload["medicine_id"],
            ReplenishmentOrder.store_id == payload["store_id"],
            ReplenishmentOrder.status == OrderStatus.suggested,
            ReplenishmentOrder.trigger_reason == "FORECAST",
        ).first()
        if existing:
            return

        shortfall = payload.get("shortfall", payload.get("predicted_demand", 100))
        suggested_qty = int(shortfall * 1.2)  # 20% buffer on top of shortfall

        order = ReplenishmentOrder(
            medicine_id=payload["medicine_id"],
            medicine_name=payload.get("medicine_name"),
            store_id=payload["store_id"],
            suggested_quantity=suggested_qty,
            trigger_reason="FORECAST",
            current_stock=payload.get("current_stock"),
            ai_confidence=payload.get("confidence_score"),
            ai_explanation=payload.get("explanation"),
            created_by="ai-forecasting-agent",
        )
        db.add(order)
        db.commit()
        logger.info(f"[REPLENISHMENT] AI suggestion created: {suggested_qty} units")
    finally:
        db.close()


def start_event_listener():
    """Start background thread to listen for inventory and AI events."""
    def listen():
        subscribe_and_handle("inventory", {
            "LOW_STOCK_ALERT": handle_low_stock_alert,
        })
    def listen_ai():
        subscribe_and_handle("replenishment", {
            "FORECAST_TRIGGERED_REPLENISHMENT": handle_forecast_replenishment,
        })
    threading.Thread(target=listen, daemon=True).start()
    threading.Thread(target=listen_ai, daemon=True).start()


# ─── Health ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"service": "replenishment-service", "status": "ok"})


# ─── Replenishment Orders ─────────────────────────────────────────────────────

@app.route("/replenishment/orders", methods=["GET"])
@require_auth
def list_orders():
    db = SessionLocal()
    try:
        q = db.query(ReplenishmentOrder)
        status = request.args.get("status")
        store_id = request.args.get("store_id")
        if status:
            q = q.filter(ReplenishmentOrder.status == status.upper())
        if store_id:
            q = q.filter(ReplenishmentOrder.store_id == store_id)
        orders = q.order_by(ReplenishmentOrder.created_at.desc()).limit(100).all()
        return jsonify({"orders": [o.to_dict() for o in orders]})
    finally:
        db.close()


@app.route("/replenishment/orders", methods=["POST"])
@require_role("admin", "supervisor", "pharmacist")
def create_order():
    """Manually create a replenishment suggestion."""
    data = request.get_json()
    required = ["medicine_id", "store_id", "suggested_quantity"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    db = SessionLocal()
    try:
        order = ReplenishmentOrder(
            medicine_id=data["medicine_id"],
            medicine_name=data.get("medicine_name"),
            store_id=data["store_id"],
            suggested_quantity=int(data["suggested_quantity"]),
            trigger_reason="MANUAL",
            current_stock=data.get("current_stock"),
            notes=data.get("notes"),
            created_by=g.user["sub"],
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        log_action(g.user["sub"], g.user["role"], "REPLENISHMENT_CREATE", str(order.id))
        return jsonify({"order": order.to_dict()}), 201
    finally:
        db.close()


@app.route("/replenishment/orders/<order_id>/approve", methods=["POST"])
@require_role("admin", "supervisor")
def approve_order(order_id):
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        order = db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id).first()
        if not order:
            return jsonify({"error": "Order not found"}), 404
        if order.status != OrderStatus.suggested:
            return jsonify({"error": f"Cannot approve order in status: {order.status.value}"}), 400

        order.status = OrderStatus.approved
        order.approved_quantity = data.get("approved_quantity", order.suggested_quantity)
        order.approved_by = g.user["sub"]
        order.notes = data.get("notes", order.notes)
        db.commit()

        log_action(g.user["sub"], g.user["role"], "REPLENISHMENT_APPROVE", str(order.id))

        # Notify procurement
        publish_event("notifications", "REPLENISHMENT_APPROVED", {
            "order_id": str(order.id),
            "medicine_name": order.medicine_name,
            "store_id": order.store_id,
            "quantity": order.approved_quantity,
        })

        return jsonify({"order": order.to_dict(), "message": "Order approved"})
    finally:
        db.close()


@app.route("/replenishment/orders/<order_id>/mark-ordered", methods=["POST"])
@require_role("admin", "supervisor")
def mark_ordered(order_id):
    db = SessionLocal()
    try:
        order = db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id).first()
        if not order:
            return jsonify({"error": "Order not found"}), 404
        order.status = OrderStatus.ordered
        db.commit()
        return jsonify({"message": "Order marked as sent to supplier"})
    finally:
        db.close()


@app.route("/replenishment/orders/<order_id>/receive", methods=["POST"])
@require_role("admin", "supervisor", "pharmacist")
def receive_order(order_id):
    db = SessionLocal()
    try:
        order = db.query(ReplenishmentOrder).filter(ReplenishmentOrder.id == order_id).first()
        if not order:
            return jsonify({"error": "Order not found"}), 404
        order.status = OrderStatus.received
        db.commit()
        log_action(g.user["sub"], g.user["role"], "REPLENISHMENT_RECEIVE", str(order.id))
        return jsonify({"message": "Order received. Remember to add stock via inventory service."})
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    start_event_listener()
    app.run(host="0.0.0.0", port=8004, debug=False)

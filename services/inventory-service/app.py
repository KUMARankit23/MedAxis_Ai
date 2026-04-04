"""
Inventory Service — Entry point.
Handles: medicine catalog, batch management, stock tracking, expiry alerts.
Port: 8002
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import logging
from datetime import date, timedelta

from flask import Flask, request, jsonify, g
from sqlalchemy import func

from database import init_db, SessionLocal
from models import Medicine, InventoryBatch, StockLedger, MedicineCategory
from shared.auth_middleware import require_auth, require_role
from shared.audit_logger import log_action
from shared.event_bus import publish_event
from shared.config import LOW_STOCK_THRESHOLD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ─── Helpers ────────────────────────────────────────────────────────────────

def get_total_stock(db, medicine_id: str, store_id: str) -> int:
    """Sum all non-quarantined, non-expired batch quantities for a medicine at a store."""
    today = date.today()
    result = db.query(func.sum(InventoryBatch.quantity)).filter(
        InventoryBatch.medicine_id == medicine_id,
        InventoryBatch.store_id == store_id,
        InventoryBatch.expiry_date > today,
        InventoryBatch.is_quarantined == False,
    ).scalar()
    return result or 0


def record_ledger(db, medicine_id, batch_id, store_id, txn_type, qty_change, qty_after, ref_id=None, user_id=None, notes=None):
    entry = StockLedger(
        medicine_id=medicine_id,
        batch_id=batch_id,
        store_id=store_id,
        transaction_type=txn_type,
        quantity_change=qty_change,
        quantity_after=qty_after,
        reference_id=ref_id,
        performed_by=user_id,
        notes=notes,
    )
    db.add(entry)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"service": "inventory-service", "status": "ok"})


# ─── Medicine Catalog ────────────────────────────────────────────────────────

@app.route("/v1/inventory/medicines", methods=["GET"])
@app.route("/inventory/medicines",    methods=["GET"])
@require_auth
def list_medicines():
    db = SessionLocal()
    try:
        q = db.query(Medicine).filter(Medicine.is_active == True)
        category = request.args.get("category")
        if category:
            q = q.filter(Medicine.category == category)
        medicines = q.all()
        return jsonify({"medicines": [m.to_dict() for m in medicines]})
    finally:
        db.close()


@app.route("/inventory/medicines", methods=["POST"])
@require_role("admin", "supervisor")
def create_medicine():
    data = request.get_json()
    required = ["name", "category", "unit_price"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    db = SessionLocal()
    try:
        med = Medicine(
            name=data["name"],
            generic_name=data.get("generic_name"),
            manufacturer=data.get("manufacturer"),
            category=MedicineCategory(data["category"]),
            unit=data.get("unit", "units"),
            unit_price=float(data["unit_price"]),
            reorder_level=data.get("reorder_level", 20),
            reorder_quantity=data.get("reorder_quantity", 100),
        )
        db.add(med)
        db.commit()
        db.refresh(med)
        log_action(g.user["sub"], g.user["role"], "MEDICINE_CREATE", str(med.id))
        return jsonify({"medicine": med.to_dict()}), 201
    finally:
        db.close()


@app.route("/inventory/medicines/<medicine_id>", methods=["GET"])
@require_auth
def get_medicine(medicine_id):
    db = SessionLocal()
    try:
        med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
        return jsonify({"medicine": med.to_dict()})
    finally:
        db.close()


# ─── Batch / Stock Management ────────────────────────────────────────────────

@app.route("/inventory/batches", methods=["POST"])
@require_role("admin", "supervisor", "pharmacist")
def receive_stock():
    """
    Receive a new stock batch.
    Records in inventory_batches and stock_ledger (RECEIVE transaction).
    """
    data = request.get_json()
    required = ["medicine_id", "batch_number", "store_id", "quantity", "expiry_date"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    db = SessionLocal()
    try:
        med = db.query(Medicine).filter(Medicine.id == data["medicine_id"]).first()
        if not med:
            return jsonify({"error": "Medicine not found"}), 404

        batch = InventoryBatch(
            medicine_id=data["medicine_id"],
            batch_number=data["batch_number"],
            store_id=data["store_id"],
            quantity=int(data["quantity"]),
            expiry_date=date.fromisoformat(data["expiry_date"]),
            purchase_price=data.get("purchase_price"),
        )
        db.add(batch)
        db.flush()  # get batch.id before commit

        total_after = get_total_stock(db, data["medicine_id"], data["store_id"]) + int(data["quantity"])
        record_ledger(
            db, data["medicine_id"], batch.id, data["store_id"],
            "RECEIVE", int(data["quantity"]), total_after,
            ref_id=data.get("po_number"), user_id=g.user["sub"]
        )
        db.commit()

        log_action(g.user["sub"], g.user["role"], "STOCK_RECEIVE", str(batch.id),
                   details={"medicine": med.name, "qty": data["quantity"]})

        # Publish event so other services can react
        publish_event("inventory", "STOCK_RECEIVED", {
            "medicine_id": data["medicine_id"],
            "store_id": data["store_id"],
            "quantity": data["quantity"],
            "batch_id": str(batch.id),
        })

        return jsonify({"batch": batch.to_dict(), "total_stock": total_after}), 201
    finally:
        db.close()


@app.route("/inventory/stock/<store_id>/<medicine_id>", methods=["GET"])
@require_auth
def get_stock_level(store_id, medicine_id):
    """Get current stock level for a medicine at a store."""
    db = SessionLocal()
    try:
        total = get_total_stock(db, medicine_id, store_id)
        med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
        if not med:
            return jsonify({"error": "Medicine not found"}), 404

        is_low = total <= med.reorder_level
        return jsonify({
            "medicine_id": medicine_id,
            "store_id": store_id,
            "total_stock": total,
            "reorder_level": med.reorder_level,
            "is_low_stock": is_low,
        })
    finally:
        db.close()


@app.route("/inventory/stock/<store_id>", methods=["GET"])
@require_auth
def get_store_stock(store_id):
    """Get all stock levels for a store."""
    db = SessionLocal()
    try:
        today = date.today()
        results = db.query(
            Medicine.id, Medicine.name, Medicine.reorder_level,
            func.sum(InventoryBatch.quantity).label("total_stock")
        ).join(InventoryBatch, Medicine.id == InventoryBatch.medicine_id).filter(
            InventoryBatch.store_id == store_id,
            InventoryBatch.expiry_date > today,
            InventoryBatch.is_quarantined == False,
        ).group_by(Medicine.id, Medicine.name, Medicine.reorder_level).all()

        stock_list = []
        for r in results:
            stock_list.append({
                "medicine_id": str(r.id),
                "name": r.name,
                "total_stock": r.total_stock or 0,
                "reorder_level": r.reorder_level,
                "is_low_stock": (r.total_stock or 0) <= r.reorder_level,
            })
        return jsonify({"store_id": store_id, "stock": stock_list})
    finally:
        db.close()


@app.route("/inventory/deduct", methods=["POST"])
@require_auth
def deduct_stock():
    """
    Deduct stock for a sale (called by billing-service).
    Uses FEFO — deducts from earliest-expiring batch first.

    Gap fixed: uses SELECT FOR UPDATE to lock rows during deduction,
    preventing race conditions when two invoices deduct the same batch
    simultaneously (serializable transaction).
    """
    data = request.get_json()
    required = ["medicine_id", "store_id", "quantity", "reference_id"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    db = SessionLocal()
    try:
        qty_needed = int(data["quantity"])
        today = date.today()

        # FEFO + SELECT FOR UPDATE — locks rows for this transaction
        # Prevents two concurrent sales from both seeing the same available stock
        from sqlalchemy import text as sa_text
        batches = db.query(InventoryBatch).filter(
            InventoryBatch.medicine_id == data["medicine_id"],
            InventoryBatch.store_id == data["store_id"],
            InventoryBatch.expiry_date > today,
            InventoryBatch.is_quarantined == False,
            InventoryBatch.quantity > 0,
        ).order_by(InventoryBatch.expiry_date.asc())

        # Apply FOR UPDATE only on PostgreSQL (SQLite doesn't support it)
        from shared.config import DB_HOST
        if DB_HOST:
            batches = batches.with_for_update()

        batches = batches.all()

        total_available = sum(b.quantity for b in batches)
        if total_available < qty_needed:
            return jsonify({
                "error": "Insufficient stock",
                "available": total_available,
                "requested": qty_needed,
            }), 409

        # Deduct across batches (FEFO order)
        remaining = qty_needed
        running_total = total_available
        for batch in batches:
            if remaining <= 0:
                break
            deduct = min(batch.quantity, remaining)
            batch.quantity -= deduct
            remaining -= deduct
            running_total -= deduct

            record_ledger(
                db, data["medicine_id"], batch.id, data["store_id"],
                "SALE", -deduct, running_total,
                ref_id=data["reference_id"],
                user_id=data.get("user_id", g.user["sub"])
            )

        db.commit()

        # Re-query total after commit for accurate low-stock check
        new_total = get_total_stock(db, data["medicine_id"], data["store_id"])
        med = db.query(Medicine).filter(Medicine.id == data["medicine_id"]).first()
        if new_total <= med.reorder_level:
            publish_event("inventory", "LOW_STOCK_ALERT", {
                "medicine_id": data["medicine_id"],
                "medicine_name": med.name,
                "store_id": data["store_id"],
                "current_stock": new_total,
                "reorder_level": med.reorder_level,
            })

        log_action(g.user["sub"], g.user["role"], "STOCK_DEDUCT", data["medicine_id"],
                   details={"qty": qty_needed, "ref": data["reference_id"],
                            "remaining": new_total})

        return jsonify({"deducted": qty_needed, "remaining_stock": new_total})
    finally:
        db.close()


# ─── Expiry Alerts ───────────────────────────────────────────────────────────

@app.route("/inventory/expiry-alerts", methods=["GET"])
@require_role("admin", "supervisor", "pharmacist")
def expiry_alerts():
    """
    Return batches expiring within the next N days with tiered severity.

    Gap fixed: tiered severity levels matching document spec:
      - 30 days → LOW
      - 15 days → MEDIUM
      - 7 days  → HIGH
    """
    days = int(request.args.get("days", 30))
    store_id = request.args.get("store_id")
    db = SessionLocal()
    try:
        today = date.today()
        cutoff = today + timedelta(days=days)
        q = db.query(InventoryBatch).filter(
            InventoryBatch.expiry_date <= cutoff,
            InventoryBatch.expiry_date >= today,
            InventoryBatch.quantity > 0,
        )
        if store_id:
            q = q.filter(InventoryBatch.store_id == store_id)
        batches = q.order_by(InventoryBatch.expiry_date.asc()).all()

        def severity(expiry):
            days_left = (expiry - today).days
            if days_left <= 7:  return "HIGH"
            if days_left <= 15: return "MEDIUM"
            return "LOW"

        result = []
        for b in batches:
            d = b.to_dict()
            d["days_to_expiry"] = (b.expiry_date - today).days
            d["severity"] = severity(b.expiry_date)
            result.append(d)

        return jsonify({
            "expiring_batches": result,
            "within_days": days,
            "counts": {
                "HIGH":   sum(1 for r in result if r["severity"] == "HIGH"),
                "MEDIUM": sum(1 for r in result if r["severity"] == "MEDIUM"),
                "LOW":    sum(1 for r in result if r["severity"] == "LOW"),
            }
        })
    finally:
        db.close()


@app.route("/inventory/adjust", methods=["POST"])
@require_role("admin", "supervisor")
def adjust_stock():
    """
    Manual stock adjustment (shrinkage, damage, audit correction).

    Gap fixed: missing adjustment workflow from document.
    Records ADJUSTMENT ledger entry with before/after state.
    """
    data = request.get_json()
    required = ["batch_id", "new_quantity", "reason"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    db = SessionLocal()
    try:
        batch = db.query(InventoryBatch).filter(
            InventoryBatch.id == data["batch_id"]
        ).first()
        if not batch:
            return jsonify({"error": "Batch not found"}), 404

        old_qty = batch.quantity
        new_qty = int(data["new_quantity"])
        if new_qty < 0:
            return jsonify({"error": "Quantity cannot be negative"}), 400

        qty_change = new_qty - old_qty
        batch.quantity = new_qty

        record_ledger(
            db, str(batch.medicine_id), batch.id, batch.store_id,
            "ADJUSTMENT", qty_change, new_qty,
            ref_id=data.get("reference_id"),
            user_id=g.user["sub"],
            notes=data["reason"],
        )
        db.commit()

        log_action(g.user["sub"], g.user["role"], "STOCK_ADJUSTMENT", str(batch.id),
                   details={"before": old_qty, "after": new_qty,
                            "change": qty_change, "reason": data["reason"]})

        return jsonify({
            "batch_id": str(batch.id),
            "before": old_qty,
            "after": new_qty,
            "change": qty_change,
            "reason": data["reason"],
        })
    finally:
        db.close()


@app.route("/inventory/low-stock", methods=["GET"])
@require_auth
def low_stock_report():
    """Return all medicines below reorder level across all stores."""
    store_id = request.args.get("store_id")
    db = SessionLocal()
    try:
        today = date.today()
        q = db.query(
            Medicine.id, Medicine.name, Medicine.reorder_level,
            InventoryBatch.store_id,
            func.sum(InventoryBatch.quantity).label("total_stock")
        ).join(InventoryBatch, Medicine.id == InventoryBatch.medicine_id).filter(
            InventoryBatch.expiry_date > today,
            InventoryBatch.is_quarantined == False,
        )
        if store_id:
            q = q.filter(InventoryBatch.store_id == store_id)
        results = q.group_by(
            Medicine.id, Medicine.name, Medicine.reorder_level, InventoryBatch.store_id
        ).having(func.sum(InventoryBatch.quantity) <= Medicine.reorder_level).all()

        return jsonify({"low_stock_items": [
            {
                "medicine_id": str(r.id),
                "name": r.name,
                "store_id": r.store_id,
                "total_stock": r.total_stock,
                "reorder_level": r.reorder_level,
            } for r in results
        ]})
    finally:
        db.close()


@app.route("/inventory/ledger/<medicine_id>", methods=["GET"])
@require_role("admin", "supervisor")
def stock_ledger(medicine_id):
    """Full audit trail for a medicine."""
    db = SessionLocal()
    try:
        entries = db.query(StockLedger).filter(
            StockLedger.medicine_id == medicine_id
        ).order_by(StockLedger.timestamp.desc()).limit(100).all()
        return jsonify({"ledger": [e.to_dict() for e in entries]})
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8002, debug=False)

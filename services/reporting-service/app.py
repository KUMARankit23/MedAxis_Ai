"""
Reporting Service — Entry point.
Provides BI/analytics APIs for dashboards.
Queries billing and inventory databases directly (read-only cross-DB queries).
Port: 8005
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import logging
from datetime import datetime, date, timedelta

import requests
from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine, text

from shared.auth_middleware import require_auth, require_role
from shared.config import get_db_url, SERVICE_PORTS
from shared.db_utils import make_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Read-only connections to billing and inventory databases
billing_engine = make_engine("medaxis_billing")
inventory_engine = make_engine("medaxis_inventory")


def run_query(engine, sql: str, params: dict = None):
    """Execute a read-only SQL query and return rows as dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        cols = result.keys()
        return [dict(zip(cols, row)) for row in result.fetchall()]


def is_postgres(engine) -> bool:
    """Check if the engine is connected to PostgreSQL."""
    return "postgresql" in str(engine.url)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"service": "reporting-service", "status": "ok"})


# ─── Sales Summary ───────────────────────────────────────────────────────────

@app.route("/reporting/sales/summary", methods=["GET"])
@require_role("admin", "supervisor")
def sales_summary():
    """
    Sales summary for a date range.
    Query params: start_date, end_date, store_id
    """
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    end = request.args.get("end_date", date.today().isoformat())
    store_id = request.args.get("store_id")

    store_filter = "AND store_id = :store_id" if store_id else ""
    sql = f"""
        SELECT
            store_id,
            DATE(created_at) as sale_date,
            COUNT(*) as invoice_count,
            SUM(total) as revenue,
            AVG(total) as avg_invoice_value
        FROM invoices
        WHERE status = 'confirmed'
          AND DATE(created_at) BETWEEN :start AND :end
          {store_filter}
        GROUP BY store_id, DATE(created_at)
        ORDER BY sale_date DESC, revenue DESC
    """
    params = {"start": start, "end": end}
    if store_id:
        params["store_id"] = store_id

    rows = run_query(billing_engine, sql, params)
    total_revenue = sum(r["revenue"] or 0 for r in rows)

    return jsonify({
        "period": {"start": start, "end": end},
        "total_revenue": round(total_revenue, 2),
        "records": rows,
    })


# ─── Top Medicines ────────────────────────────────────────────────────────────

@app.route("/reporting/medicines/top", methods=["GET"])
@require_role("admin", "supervisor")
def top_medicines():
    """Top N medicines by quantity sold."""
    limit = int(request.args.get("limit", 10))
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    end = request.args.get("end_date", date.today().isoformat())

    sql = """
        SELECT
            ii.medicine_name,
            ii.medicine_id,
            SUM(ii.quantity) as total_quantity,
            SUM(ii.line_total) as total_revenue,
            COUNT(DISTINCT ii.invoice_id) as invoice_count
        FROM invoice_items ii
        JOIN invoices i ON ii.invoice_id = i.id
        WHERE i.status = 'confirmed'
          AND DATE(i.created_at) BETWEEN :start AND :end
        GROUP BY ii.medicine_name, ii.medicine_id
        ORDER BY total_quantity DESC
        LIMIT :limit
    """
    rows = run_query(billing_engine, sql, {"start": start, "end": end, "limit": limit})
    return jsonify({"top_medicines": rows, "period": {"start": start, "end": end}})


# ─── Store Performance ────────────────────────────────────────────────────────

@app.route("/reporting/stores/performance", methods=["GET"])
@require_role("admin", "supervisor")
def store_performance():
    """Compare performance across all stores."""
    start = request.args.get("start_date", (date.today() - timedelta(days=30)).isoformat())
    end = request.args.get("end_date", date.today().isoformat())

    sql = """
        SELECT
            store_id,
            COUNT(*) as total_invoices,
            SUM(total) as total_revenue,
            AVG(total) as avg_sale,
            MAX(total) as max_sale,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_count,
            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count
        FROM invoices
        WHERE DATE(created_at) BETWEEN :start AND :end
        GROUP BY store_id
        ORDER BY total_revenue DESC
    """
    rows = run_query(billing_engine, sql, {"start": start, "end": end})
    return jsonify({"store_performance": rows, "period": {"start": start, "end": end}})


# ─── Low Stock Report ─────────────────────────────────────────────────────────

@app.route("/reporting/inventory/low-stock", methods=["GET"])
@require_role("admin", "supervisor")
def low_stock_report():
    """Medicines below reorder level across all stores."""
    sql = """
        SELECT
            m.name as medicine_name,
            m.category,
            ib.store_id,
            SUM(ib.quantity) as current_stock,
            m.reorder_level,
            m.reorder_quantity as suggested_order_qty
        FROM medicines m
        JOIN inventory_batches ib ON m.id = ib.medicine_id
        WHERE ib.expiry_date > CURRENT_DATE
          AND ib.is_quarantined = false
        GROUP BY m.name, m.category, ib.store_id, m.reorder_level, m.reorder_quantity
        HAVING SUM(ib.quantity) <= m.reorder_level
        ORDER BY current_stock ASC
    """
    rows = run_query(inventory_engine, sql)
    return jsonify({"low_stock_items": rows, "count": len(rows)})


# ─── Expiry Report ────────────────────────────────────────────────────────────

@app.route("/v1/reporting/inventory/expiry", methods=["GET"])
@app.route("/reporting/inventory/expiry",    methods=["GET"])
@require_role("admin", "supervisor")
def expiry_report():
    """Batches expiring within N days — PostgreSQL and SQLite compatible."""
    days = int(request.args.get("days", 90))

    # Use correct interval syntax per DB engine
    if is_postgres(inventory_engine):
        date_expr = f"CURRENT_DATE + INTERVAL '{days} days'"
    else:
        date_expr = f"date(CURRENT_DATE, '+{days} days')"

    sql = f"""
        SELECT
            m.name as medicine_name,
            ib.batch_number,
            ib.store_id,
            ib.quantity,
            ib.expiry_date,
            (ib.expiry_date - CURRENT_DATE) as days_to_expiry
        FROM inventory_batches ib
        JOIN medicines m ON ib.medicine_id = m.id
        WHERE ib.expiry_date BETWEEN CURRENT_DATE AND {date_expr}
          AND ib.quantity > 0
        ORDER BY ib.expiry_date ASC
    """
    rows = run_query(inventory_engine, sql)
    for r in rows:
        if hasattr(r.get("days_to_expiry"), "days"):
            r["days_to_expiry"] = r["days_to_expiry"].days
    return jsonify({"expiring_batches": rows, "within_days": days})


# ─── Dashboard Summary ────────────────────────────────────────────────────────

@app.route("/reporting/dashboard", methods=["GET"])
@require_role("admin", "supervisor")
def dashboard():
    """Single endpoint for dashboard KPIs."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    month_start = date.today().replace(day=1).isoformat()

    # Today's revenue
    today_sql = """
        SELECT COALESCE(SUM(total), 0) as revenue, COUNT(*) as invoices
        FROM invoices WHERE status = 'confirmed' AND DATE(created_at) = :today
    """
    today_data = run_query(billing_engine, today_sql, {"today": today})

    # Month revenue
    month_sql = """
        SELECT COALESCE(SUM(total), 0) as revenue, COUNT(*) as invoices
        FROM invoices WHERE status = 'confirmed' AND DATE(created_at) >= :start
    """
    month_data = run_query(billing_engine, month_sql, {"start": month_start})

    # Low stock count
    low_stock_sql = """
        SELECT COUNT(*) as count FROM (
            SELECT m.id FROM medicines m
            JOIN inventory_batches ib ON m.id = ib.medicine_id
            WHERE ib.expiry_date > CURRENT_DATE AND ib.is_quarantined = false
            GROUP BY m.id, m.reorder_level
            HAVING SUM(ib.quantity) <= m.reorder_level
        ) sub
    """
    low_stock_data = run_query(inventory_engine, low_stock_sql)

    # Expiring soon (30 days) — DB-agnostic
    if is_postgres(inventory_engine):
        expiry_where = "expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'"
    else:
        expiry_where = "expiry_date BETWEEN CURRENT_DATE AND date(CURRENT_DATE, '+30 days')"

    expiry_sql = f"""
        SELECT COUNT(*) as count FROM inventory_batches
        WHERE {expiry_where} AND quantity > 0
    """
    expiry_data = run_query(inventory_engine, expiry_sql)

    return jsonify({
        "today": {
            "revenue": round(today_data[0]["revenue"], 2) if today_data else 0,
            "invoices": today_data[0]["invoices"] if today_data else 0,
        },
        "this_month": {
            "revenue": round(month_data[0]["revenue"], 2) if month_data else 0,
            "invoices": month_data[0]["invoices"] if month_data else 0,
        },
        "alerts": {
            "low_stock_items": low_stock_data[0]["count"] if low_stock_data else 0,
            "expiring_soon_batches": expiry_data[0]["count"] if expiry_data else 0,
        },
        "generated_at": datetime.utcnow().isoformat(),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8005, debug=False)

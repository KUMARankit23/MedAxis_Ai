"""Reporting Service — BI analytics endpoints."""
import csv
import io
import json
import os
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from datetime import date, datetime, timedelta
from typing import Optional
from app.config import BILLING_DB_URL, INVENTORY_DB_URL, JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Redis cache ───────────────────────────────────────────────────────────────

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT  = int(os.getenv("REDIS_PORT", "6379"))

_redis_client = None


def _get_redis():
    """Return a redis.asyncio client (lazy init, non-blocking)."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"Redis client init failed: {e}")
    return _redis_client


async def _cache_get(key: str):
    try:
        r = _get_redis()
        if r:
            val = await r.get(key)
            if val:
                return json.loads(val)
    except Exception as e:
        logger.warning(f"Redis GET failed for key '{key}': {e}")
    return None


async def _cache_set(key: str, value, ttl_seconds: int):
    try:
        r = _get_redis()
        if r:
            await r.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as e:
        logger.warning(f"Redis SET failed for key '{key}': {e}")


# ── DB engines ────────────────────────────────────────────────────────────────

_billing_engine = None
_inventory_engine = None


def _get_billing_engine():
    global _billing_engine
    if _billing_engine is None:
        url = BILLING_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
        _billing_engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    return _billing_engine


def _get_inventory_engine():
    global _inventory_engine
    if _inventory_engine is None:
        url = INVENTORY_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
        _inventory_engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    return _inventory_engine


def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        p = pyjwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if p.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return p
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail=f"Required roles: {list(roles)}")
        return user
    return dep


async def run_query(engine, sql: str, params: dict = None):
    """Execute a raw SQL query, converting string dates to date objects for asyncpg."""
    from datetime import date as date_type
    if params:
        converted = {}
        for k, v in params.items():
            if isinstance(v, str) and len(v) == 10:
                try:
                    converted[k] = date_type.fromisoformat(v)
                except ValueError:
                    converted[k] = v
            else:
                converted[k] = v
        params = converted
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


def _rows_to_csv(rows: list, filename: str) -> StreamingResponse:
    """Convert a list of dicts to a CSV StreamingResponse."""
    if not rows:
        content = ""
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        content = output.getvalue()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Dashboard KPIs ────────────────────────────────────────────────────────────

@router.get("/reporting/dashboard", tags=["Dashboard"])
async def dashboard(user=Depends(require_role("admin", "supervisor"))):
    cache_key = "dashboard:cache"
    cached = await _cache_get(cache_key)
    if cached:
        cached["_cached"] = True
        return cached

    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    today_data = await run_query(
        _get_billing_engine(),
        "SELECT COALESCE(SUM(total),0) AS revenue, COUNT(*) AS invoices "
        "FROM invoices WHERE status='confirmed' AND DATE(created_at)=:today",
        {"today": today},
    )
    month_data = await run_query(
        _get_billing_engine(),
        "SELECT COALESCE(SUM(total),0) AS revenue, COUNT(*) AS invoices "
        "FROM invoices WHERE status='confirmed' AND DATE(created_at)>=:start",
        {"start": month_start},
    )
    low_stock = await run_query(
        _get_inventory_engine(),
        "SELECT COUNT(*) AS count FROM ("
        "  SELECT m.id FROM medicines m "
        "  JOIN inventory_batches ib ON m.id=ib.medicine_id "
        "  WHERE ib.expiry_date>CURRENT_DATE AND ib.is_quarantined=false "
        "  GROUP BY m.id, m.reorder_level "
        "  HAVING SUM(ib.quantity)<=m.reorder_level"
        ") sub",
    )
    expiring = await run_query(
        _get_inventory_engine(),
        "SELECT COUNT(*) AS count FROM inventory_batches "
        "WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+INTERVAL '30 days' AND quantity>0",
    )

    result = {
        "today": {
            "revenue": round(float(today_data[0]["revenue"]), 2),
            "invoices": today_data[0]["invoices"],
        },
        "this_month": {
            "revenue": round(float(month_data[0]["revenue"]), 2),
            "invoices": month_data[0]["invoices"],
        },
        "alerts": {
            "low_stock_items": low_stock[0]["count"],
            "expiring_soon_batches": expiring[0]["count"],
        },
        "generated_at": datetime.utcnow().isoformat(),
    }

    await _cache_set(cache_key, result, ttl_seconds=300)  # 5 minutes
    return result


# ── Sales Summary ─────────────────────────────────────────────────────────────

@router.get("/reporting/sales/summary", tags=["Sales"])
async def sales_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    outlet_id: Optional[str] = None,
    format: Optional[str] = None,
    user=Depends(require_role("admin", "supervisor")),
):
    start = start_date or (date.today() - timedelta(days=30)).isoformat()
    end = end_date or date.today().isoformat()
    outlet_filter = "AND outlet_id=:outlet_id" if outlet_id else ""
    params = {"start": start, "end": end}
    if outlet_id:
        params["outlet_id"] = outlet_id

    rows = await run_query(
        _get_billing_engine(),
        f"SELECT outlet_id, DATE(created_at) AS sale_date, "
        f"COUNT(*) AS invoice_count, "
        f"SUM(total) AS revenue, "
        f"AVG(total) AS avg_invoice_value "
        f"FROM invoices "
        f"WHERE status='confirmed' AND DATE(created_at) BETWEEN :start AND :end {outlet_filter} "
        f"GROUP BY outlet_id, DATE(created_at) "
        f"ORDER BY sale_date DESC",
        params,
    )
    for r in rows:
        r["revenue"] = round(float(r["revenue"] or 0), 2)
        r["avg_invoice_value"] = round(float(r["avg_invoice_value"] or 0), 2)
        r["sale_date"] = str(r["sale_date"])

    if format and format.lower() == "csv":
        return _rows_to_csv(rows, "sales_summary.csv")

    return {
        "period": {"start": start, "end": end},
        "total_revenue": round(sum(r["revenue"] for r in rows), 2),
        "records": rows,
    }


# ── Top Products ──────────────────────────────────────────────────────────────

@router.get("/reporting/sales/top-products", tags=["Sales"])
async def top_products(
    limit: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user=Depends(require_role("admin", "supervisor")),
):
    start = start_date or (date.today() - timedelta(days=30)).isoformat()
    end = end_date or date.today().isoformat()

    cache_key = f"top_products:{start}:{end}:{limit}"
    cached = await _cache_get(cache_key)
    if cached:
        cached["_cached"] = True
        return cached

    rows = await run_query(
        _get_billing_engine(),
        "SELECT ii.medicine_name, ii.medicine_id, "
        "SUM(ii.quantity) AS total_quantity, "
        "SUM(ii.line_total) AS total_revenue "
        "FROM invoice_items ii "
        "JOIN invoices i ON ii.invoice_id=i.id "
        "WHERE i.status='confirmed' AND DATE(i.created_at) BETWEEN :start AND :end "
        "GROUP BY ii.medicine_name, ii.medicine_id "
        "ORDER BY total_quantity DESC "
        "LIMIT :limit",
        {"start": start, "end": end, "limit": limit},
    )
    for r in rows:
        r["total_revenue"] = round(float(r["total_revenue"] or 0), 2)
        r["total_quantity"] = int(r["total_quantity"] or 0)

    result = {"top_medicines": rows, "period": {"start": start, "end": end}}
    await _cache_set(cache_key, result, ttl_seconds=600)  # 10 minutes
    return result


# ── Store Performance ─────────────────────────────────────────────────────────

@router.get("/reporting/stores/performance", tags=["Stores"])
async def store_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    format: Optional[str] = None,
    user=Depends(require_role("admin", "supervisor")),
):
    start = start_date or (date.today() - timedelta(days=30)).isoformat()
    end = end_date or date.today().isoformat()

    rows = await run_query(
        _get_billing_engine(),
        "SELECT outlet_id AS store_id, "
        "COUNT(*) AS total_invoices, "
        "SUM(total) AS total_revenue, "
        "AVG(total) AS avg_sale, "
        "SUM(CASE WHEN status='confirmed' THEN 1 ELSE 0 END) AS confirmed_count, "
        "SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled_count "
        "FROM invoices "
        "WHERE DATE(created_at) BETWEEN :start AND :end "
        "GROUP BY outlet_id "
        "ORDER BY total_revenue DESC",
        {"start": start, "end": end},
    )
    for r in rows:
        r["total_revenue"] = round(float(r["total_revenue"] or 0), 2)
        r["avg_sale"] = round(float(r["avg_sale"] or 0), 2)

    if format and format.lower() == "csv":
        return _rows_to_csv(rows, "store_performance.csv")

    return {"store_performance": rows, "period": {"start": start, "end": end}}


# ── Low Stock Report ──────────────────────────────────────────────────────────

@router.get("/reporting/inventory/low-stock", tags=["Inventory"])
async def low_stock_report(user=Depends(require_role("admin", "supervisor"))):
    rows = await run_query(
        _get_inventory_engine(),
        "SELECT m.name, m.category, ib.outlet_id AS store_id, "
        "SUM(ib.quantity) AS current_stock, "
        "m.reorder_level, "
        "m.reorder_quantity AS suggested_order_qty "
        "FROM medicines m "
        "JOIN inventory_batches ib ON m.id=ib.medicine_id "
        "WHERE ib.expiry_date>CURRENT_DATE AND ib.is_quarantined=false "
        "GROUP BY m.name, m.category, ib.outlet_id, m.reorder_level, m.reorder_quantity "
        "HAVING SUM(ib.quantity)<=m.reorder_level "
        "ORDER BY current_stock ASC",
    )
    return {"low_stock_items": rows, "count": len(rows)}


# ── Expiry Report ─────────────────────────────────────────────────────────────

@router.get("/reporting/inventory/expiry", tags=["Inventory"])
async def expiry_report(
    days: int = 90,
    user=Depends(require_role("admin", "supervisor")),
):
    rows = await run_query(
        _get_inventory_engine(),
        f"SELECT m.name AS medicine_name, ib.batch_number, ib.outlet_id AS store_id, "
        f"ib.quantity, ib.expiry_date, "
        f"(ib.expiry_date - CURRENT_DATE) AS days_to_expiry "
        f"FROM inventory_batches ib "
        f"JOIN medicines m ON ib.medicine_id=m.id "
        f"WHERE ib.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+INTERVAL '{int(days)} days' "
        f"AND ib.quantity>0 "
        f"ORDER BY ib.expiry_date ASC",
    )
    for r in rows:
        if hasattr(r.get("days_to_expiry"), "days"):
            r["days_to_expiry"] = r["days_to_expiry"].days
        r["expiry_date"] = str(r["expiry_date"])

    return {"expiring_batches": rows, "within_days": days}

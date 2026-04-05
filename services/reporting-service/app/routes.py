"""Reporting Service — BI analytics endpoints."""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from datetime import date, datetime, timedelta
from typing import Optional
from app.config import BILLING_DB_URL, INVENTORY_DB_URL, JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

router = APIRouter()

billing_engine   = create_async_engine(BILLING_DB_URL.replace("postgresql://","postgresql+asyncpg://"), echo=False)
inventory_engine = create_async_engine(INVENTORY_DB_URL.replace("postgresql://","postgresql+asyncpg://"), echo=False)

def get_current_user(request: Request):
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "): raise HTTPException(401,"Missing token")
    try:
        p = pyjwt.decode(auth.split(" ",1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if p.get("type") != "access": raise HTTPException(401,"Invalid token type")
        return p
    except: raise HTTPException(401,"Invalid or expired token")

def require_role(*roles):
    def dep(user=Depends(get_current_user)):
        if user.get("role") not in roles: raise HTTPException(403,f"Required: {list(roles)}")
        return user
    return dep

async def run_query(engine, sql: str, params: dict = None):
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        cols = result.keys()
        return [dict(zip(cols, row)) for row in result.fetchall()]

@router.get("/reporting/dashboard", tags=["Dashboard"])
async def dashboard(user=Depends(require_role("admin","supervisor"))):
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    today_data  = await run_query(billing_engine, "SELECT COALESCE(SUM(total),0) as revenue, COUNT(*) as invoices FROM invoices WHERE status='confirmed' AND DATE(created_at)=:today", {"today":today})
    month_data  = await run_query(billing_engine, "SELECT COALESCE(SUM(total),0) as revenue, COUNT(*) as invoices FROM invoices WHERE status='confirmed' AND DATE(created_at)>=:start", {"start":month_start})
    low_stock   = await run_query(inventory_engine, "SELECT COUNT(*) as count FROM (SELECT m.id FROM medicines m JOIN inventory_batches ib ON m.id=ib.medicine_id WHERE ib.expiry_date>CURRENT_DATE AND ib.is_quarantined=false GROUP BY m.id,m.reorder_level HAVING SUM(ib.quantity)<=m.reorder_level) sub")
    expiring    = await run_query(inventory_engine, "SELECT COUNT(*) as count FROM inventory_batches WHERE expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+INTERVAL '30 days' AND quantity>0")
    return {"today":{"revenue":round(today_data[0]["revenue"],2),"invoices":today_data[0]["invoices"]},
            "this_month":{"revenue":round(month_data[0]["revenue"],2),"invoices":month_data[0]["invoices"]},
            "alerts":{"low_stock_items":low_stock[0]["count"],"expiring_soon_batches":expiring[0]["count"]},
            "generated_at":datetime.utcnow().isoformat()}

@router.get("/reporting/sales/summary", tags=["Sales"])
async def sales_summary(start_date: Optional[str]=None, end_date: Optional[str]=None,
                         outlet_id: Optional[str]=None, user=Depends(require_role("admin","supervisor"))):
    start = start_date or (date.today()-timedelta(days=30)).isoformat()
    end   = end_date   or date.today().isoformat()
    sf = "AND outlet_id=:outlet_id" if outlet_id else ""
    rows = await run_query(billing_engine, f"SELECT outlet_id,DATE(created_at) as sale_date,COUNT(*) as invoice_count,SUM(total) as revenue,AVG(total) as avg_value FROM invoices WHERE status='confirmed' AND DATE(created_at) BETWEEN :start AND :end {sf} GROUP BY outlet_id,DATE(created_at) ORDER BY sale_date DESC", {"start":start,"end":end,**({"outlet_id":outlet_id} if outlet_id else {})})
    return {"period":{"start":start,"end":end},"total_revenue":round(sum(r["revenue"] or 0 for r in rows),2),"records":rows}

@router.get("/reporting/sales/top-products", tags=["Sales"])
async def top_products(limit: int=10, start_date: Optional[str]=None, end_date: Optional[str]=None,
                        user=Depends(require_role("admin","supervisor"))):
    start = start_date or (date.today()-timedelta(days=30)).isoformat()
    end   = end_date   or date.today().isoformat()
    rows = await run_query(billing_engine, "SELECT ii.medicine_name,ii.medicine_id,SUM(ii.quantity) as total_qty,SUM(ii.line_total) as total_revenue FROM invoice_items ii JOIN invoices i ON ii.invoice_id=i.id WHERE i.status='confirmed' AND DATE(i.created_at) BETWEEN :start AND :end GROUP BY ii.medicine_name,ii.medicine_id ORDER BY total_qty DESC LIMIT :limit", {"start":start,"end":end,"limit":limit})
    return {"top_products":rows,"period":{"start":start,"end":end}}

@router.get("/reporting/stores/performance", tags=["Stores"])
async def store_performance(start_date: Optional[str]=None, end_date: Optional[str]=None,
                              user=Depends(require_role("admin","supervisor"))):
    start = start_date or (date.today()-timedelta(days=30)).isoformat()
    end   = end_date   or date.today().isoformat()
    rows = await run_query(billing_engine, "SELECT outlet_id,COUNT(*) as total_invoices,SUM(total) as total_revenue,AVG(total) as avg_sale,SUM(CASE WHEN status='confirmed' THEN 1 ELSE 0 END) as confirmed,SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) as cancelled FROM invoices WHERE DATE(created_at) BETWEEN :start AND :end GROUP BY outlet_id ORDER BY total_revenue DESC", {"start":start,"end":end})
    return {"store_performance":rows,"period":{"start":start,"end":end}}

@router.get("/reporting/inventory/low-stock", tags=["Inventory"])
async def low_stock_report(user=Depends(require_role("admin","supervisor"))):
    rows = await run_query(inventory_engine, "SELECT m.name,m.category,ib.outlet_id,SUM(ib.quantity) as current_stock,m.reorder_level,m.reorder_quantity as suggested_order FROM medicines m JOIN inventory_batches ib ON m.id=ib.medicine_id WHERE ib.expiry_date>CURRENT_DATE AND ib.is_quarantined=false GROUP BY m.name,m.category,ib.outlet_id,m.reorder_level,m.reorder_quantity HAVING SUM(ib.quantity)<=m.reorder_level ORDER BY current_stock ASC")
    return {"low_stock_items":rows,"count":len(rows)}

@router.get("/reporting/inventory/expiry", tags=["Inventory"])
async def expiry_report(days: int=90, user=Depends(require_role("admin","supervisor"))):
    rows = await run_query(inventory_engine, f"SELECT m.name,ib.batch_number,ib.outlet_id,ib.quantity,ib.expiry_date,(ib.expiry_date-CURRENT_DATE) as days_to_expiry FROM inventory_batches ib JOIN medicines m ON ib.medicine_id=m.id WHERE ib.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE+INTERVAL '{days} days' AND ib.quantity>0 ORDER BY ib.expiry_date ASC")
    for r in rows:
        if hasattr(r.get("days_to_expiry"),"days"): r["days_to_expiry"] = r["days_to_expiry"].days
    return {"expiring_batches":rows,"within_days":days}

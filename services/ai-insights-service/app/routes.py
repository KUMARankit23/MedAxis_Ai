"""AI Insights Service — FastAPI routes for all three agents."""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional
import httpx
import os
import time
import logging
from app.database import get_db
from app.models import ForecastResult, AnomalyLog
from app.agents.demand_forecasting import forecast_demand
from app.agents.anomaly_detection import detect_sales_anomalies, detect_stock_mismatch
from app.agents.conversational import process_query
from app.config import JWT_SECRET, JWT_ALGORITHM
import jwt as pyjwt

router = APIRouter()
logger = logging.getLogger(__name__)

NOTIFICATION_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8007")

# ── Per-user rate limit for NL queries (10/min) ───────────────────────────────
_query_rate_store: dict = {}   # {user_id: [timestamps]}
QUERY_RATE_LIMIT = 10
QUERY_RATE_WINDOW = 60   # seconds


def _is_query_rate_limited(user_id: str) -> bool:
    now = time.time()
    window_start = now - QUERY_RATE_WINDOW
    timestamps = _query_rate_store.get(user_id, [])
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= QUERY_RATE_LIMIT:
        _query_rate_store[user_id] = timestamps
        return True
    timestamps.append(now)
    _query_rate_store[user_id] = timestamps
    return False


async def _notify(notification_type: str, message: str, subject: str = None):
    """Fire-and-forget notification to the notification service."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(
                f"{NOTIFICATION_URL}/notifications",
                json={
                    "notification_type": notification_type,
                    "message": message,
                    "subject": subject or notification_type,
                    "source_service": "ai-insights-service",
                },
            )
    except Exception as e:
        logger.warning(f"Notification dispatch failed: {e}")


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


# ── Model metadata ────────────────────────────────────────────────────────────

@router.get("/ai/models", tags=["Models"])
async def list_models():
    """Returns metadata about available AI models — no auth required."""
    return {
        "models": [
            {
                "name": "demand_forecasting",
                "algorithm": "LinearRegression",
                "fallback": "moving_average_7d",
                "description": "7-day demand forecast per medicine per outlet using historical sales data.",
                "inputs": ["medicine_id", "outlet_id", "sales_history", "current_stock"],
                "outputs": ["forecasts", "total_predicted", "confidence_score", "explanation"],
            },
            {
                "name": "anomaly_detection",
                "algorithm": "IsolationForest",
                "fallback": "iqr_rule_based",
                "description": "Detects sales spikes, drops, and stock mismatches using unsupervised ML.",
                "inputs": ["medicine_id", "outlet_id", "sales_history"],
                "outputs": ["anomalies_detected", "anomalies", "severity"],
            },
            {
                "name": "conversational_query",
                "algorithm": "pattern_matching",
                "fallback": "openai_gpt",
                "description": "Converts natural language questions to read-only SQL queries.",
                "inputs": ["query"],
                "outputs": ["generated_sql", "explanation", "target_db", "method"],
                "guardrails": ["SELECT-only", "parameterized queries", "schema-constrained"],
            },
        ]
    }


# ── Demand Forecasting Agent ──────────────────────────────────────────────────

@router.post("/ai/forecast", tags=["Forecasting"])
async def run_forecast(
    body: dict,
    user=Depends(require_role("admin", "supervisor", "pharmacist", "inventory_planner")),
    db: AsyncSession = Depends(get_db),
):
    required = ["medicine_id", "outlet_id", "sales_history"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=400, detail=f"Required fields: {required}")

    result = forecast_demand(
        medicine_id=body["medicine_id"],
        outlet_id=body["outlet_id"],
        medicine_name=body.get("medicine_name", "Unknown"),
        sales_history=body["sales_history"],
        forecast_days=body.get("forecast_days", 7),
    )

    current_stock = body.get("current_stock", 0)
    triggered = current_stock > 0 and result["total_predicted"] > current_stock

    for f in result["forecasts"]:
        db.add(ForecastResult(
            medicine_id=body["medicine_id"],
            medicine_name=body.get("medicine_name"),
            outlet_id=body["outlet_id"],
            forecast_date=date.fromisoformat(f["date"]),
            predicted_demand=f["predicted_demand"],
            confidence_score=result["confidence_score"],
            model_used=result["model_used"],
            explanation=result["explanation"],
            triggered_replenishment=triggered,
        ))

    await db.commit()

    result["triggered_replenishment"] = triggered
    if triggered:
        result["replenishment_note"] = (
            f"Predicted demand ({result['total_predicted']}) exceeds current stock ({current_stock}). "
            "Consider raising a replenishment order."
        )
        await _notify(
            "REPLENISHMENT",
            result["replenishment_note"],
            subject=f"Replenishment needed: {body.get('medicine_name', body['medicine_id'])}",
        )
    return result


@router.get("/ai/forecasts", tags=["Forecasting"])
async def get_forecasts(
    medicine_id: Optional[str] = None,
    outlet_id: Optional[str] = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(ForecastResult)
        .where(ForecastResult.forecast_date >= date.today())
        .order_by(ForecastResult.forecast_date)
        .limit(100)
    )
    if medicine_id:
        q = q.where(ForecastResult.medicine_id == medicine_id)
    if outlet_id:
        q = q.where(ForecastResult.outlet_id == outlet_id)
    result = await db.execute(q)
    return [
        {
            "id": str(f.id), "medicine_id": f.medicine_id, "medicine_name": f.medicine_name,
            "outlet_id": f.outlet_id, "forecast_date": f.forecast_date.isoformat(),
            "predicted_demand": f.predicted_demand, "confidence_score": f.confidence_score,
            "model_used": f.model_used, "explanation": f.explanation,
            "triggered_replenishment": f.triggered_replenishment,
        }
        for f in result.scalars().all()
    ]


# ── Anomaly Detection Agent ───────────────────────────────────────────────────

@router.post("/ai/anomalies/detect", tags=["Anomaly Detection"])
async def detect_anomalies(
    body: dict,
    user=Depends(require_role("admin", "supervisor", "pharmacist")),
    db: AsyncSession = Depends(get_db),
):
    required = ["medicine_id", "outlet_id", "sales_history"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=400, detail=f"Required fields: {required}")

    anomalies = detect_sales_anomalies(
        medicine_id=body["medicine_id"],
        outlet_id=body["outlet_id"],
        medicine_name=body.get("medicine_name", "Unknown"),
        sales_history=body["sales_history"],
    )

    for a in anomalies:
        db.add(AnomalyLog(
            anomaly_type=a["anomaly_type"],
            medicine_id=a["medicine_id"],
            outlet_id=a["outlet_id"],
            severity=a["severity"],
            description=a["description"],
            detected_value=a.get("detected_value"),
            expected_range=a.get("expected_range"),
        ))
    await db.commit()

    for a in anomalies:
        await _notify(
            "ANOMALY",
            a["description"],
            subject=f"[{a['severity']}] {a['anomaly_type']} detected",
        )

    return {
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies,
        "message": f"Detected {len(anomalies)} anomalies." if anomalies else "No anomalies detected.",
    }


@router.post("/ai/anomalies/stock-mismatch", tags=["Anomaly Detection"])
async def stock_mismatch(
    body: dict,
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    required = ["medicine_id", "outlet_id", "system_stock", "physical_count"]
    if not all(k in body for k in required):
        raise HTTPException(status_code=400, detail=f"Required fields: {required}")

    anomaly = detect_stock_mismatch(
        body["medicine_id"], body["outlet_id"],
        body.get("medicine_name", "Unknown"),
        int(body["system_stock"]), int(body["physical_count"]),
    )
    if not anomaly:
        return {"mismatch_detected": False, "message": "Within acceptable tolerance."}

    db.add(AnomalyLog(
        anomaly_type=anomaly["anomaly_type"],
        medicine_id=anomaly["medicine_id"],
        outlet_id=anomaly["outlet_id"],
        severity=anomaly["severity"],
        description=anomaly["description"],
        detected_value=anomaly.get("detected_value"),
        expected_range=anomaly.get("expected_range"),
    ))
    await db.commit()
    return {"mismatch_detected": True, "anomaly": anomaly}


@router.get("/ai/anomalies", tags=["Anomaly Detection"])
async def list_anomalies(
    severity: Optional[str] = None,
    outlet_id: Optional[str] = None,
    resolved: bool = False,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(AnomalyLog)
        .where(AnomalyLog.is_resolved == resolved)
        .order_by(AnomalyLog.detected_at.desc())
        .limit(100)
    )
    if severity:
        q = q.where(AnomalyLog.severity == severity.upper())
    if outlet_id:
        q = q.where(AnomalyLog.outlet_id == outlet_id)
    result = await db.execute(q)
    return [
        {
            "id": str(l.id), "anomaly_type": l.anomaly_type,
            "medicine_id": l.medicine_id, "outlet_id": l.outlet_id,
            "severity": l.severity, "description": l.description,
            "detected_value": l.detected_value, "expected_range": l.expected_range,
            "is_resolved": l.is_resolved, "detected_at": l.detected_at.isoformat(),
        }
        for l in result.scalars().all()
    ]


@router.post("/ai/anomalies/{anomaly_id}/resolve", tags=["Anomaly Detection"])
async def resolve_anomaly(
    anomaly_id: str,
    body: dict = {},
    user=Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    result = await db.execute(select(AnomalyLog).where(AnomalyLog.id == anomaly_id))
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    log.is_resolved = True
    log.resolution_notes = body.get("notes", "Resolved via dashboard")
    log.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Anomaly resolved", "anomaly_id": anomaly_id}


# ── Conversational Agent ──────────────────────────────────────────────────────

@router.post("/ai/query", tags=["Conversational AI"])
async def nl_query(
    body: dict,
    user=Depends(require_role("admin", "supervisor")),
):
    if "query" not in body:
        raise HTTPException(status_code=400, detail="Body must contain 'query' field")
    if len(body["query"].strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short")

    # Per-user rate limiting
    if _is_query_rate_limited(user["sub"]):
        raise HTTPException(
            status_code=429,
            detail=f"AI query rate limit: {QUERY_RATE_LIMIT} requests/minute. Please wait before trying again.",
        )

    result = process_query(body["query"])
    if not result.get("matched"):
        raise HTTPException(
            status_code=422,
            detail={
                "error": result.get("error", "Could not understand query"),
                "suggestion": result.get("suggestion"),
                "examples": result.get("example_queries", []),
            },
        )
    return {
        "query": body["query"],
        "generated_sql": result.get("sql"),
        "explanation": result.get("explanation"),
        "target_db": result.get("db"),
        "method": result.get("method"),
    }

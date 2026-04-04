"""
AI Insights Service — Entry point.
Hosts three active AI agents:
  1. Demand Forecasting Agent → predicts 7-day demand, triggers replenishment
  2. Anomaly Detection Agent → detects sales spikes and stock mismatches
  3. Conversational Agent → NLP → SQL query interface
Port: 8006
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import logging
from datetime import date, timedelta

from flask import Flask, request, jsonify, g

from database import init_db, SessionLocal
from models import ForecastResult, AnomalyLog
from agents.demand_forecasting_agent import forecast_demand
from agents.anomaly_detection_agent import detect_sales_anomalies, detect_stock_mismatch
from agents.conversational_agent import process_query
from shared.auth_middleware import require_auth, require_role
from shared.event_bus import publish_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"service": "ai-insights-service", "status": "ok"})


# ─── Demand Forecasting Agent ─────────────────────────────────────────────────

@app.route("/ai/forecast", methods=["POST"])
@require_role("admin", "supervisor", "pharmacist")
def run_forecast():
    """
    Run demand forecasting for a medicine at a store.

    Body:
    {
      "medicine_id": "...",
      "medicine_name": "Paracetamol 500mg",
      "store_id": "STORE-001",
      "sales_history": [{"date": "2024-01-01", "quantity": 25}, ...],
      "forecast_days": 7,
      "current_stock": 50  // optional: triggers replenishment if forecast > stock
    }
    """
    data = request.get_json()
    required = ["medicine_id", "store_id", "sales_history"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    result = forecast_demand(
        medicine_id=data["medicine_id"],
        store_id=data["store_id"],
        medicine_name=data.get("medicine_name", "Unknown"),
        sales_history=data["sales_history"],
        forecast_days=data.get("forecast_days", 7),
    )

    db = SessionLocal()
    try:
        # Persist forecast results
        saved_forecasts = []
        for f in result["forecasts"]:
            fr = ForecastResult(
                medicine_id=data["medicine_id"],
                medicine_name=data.get("medicine_name"),
                store_id=data["store_id"],
                forecast_date=date.fromisoformat(f["date"]),
                predicted_demand=f["predicted_demand"],
                confidence_score=result["confidence_score"],
                model_used=result["model_used"],
                explanation=result["explanation"],
            )
            db.add(fr)
            saved_forecasts.append(fr)

        # AI ACTION: if total predicted demand > current stock, trigger replenishment
        current_stock = data.get("current_stock", 0)
        triggered_replenishment = False
        if current_stock > 0 and result["total_predicted"] > current_stock:
            triggered_replenishment = True
            for fr in saved_forecasts:
                fr.triggered_replenishment = True

            publish_event("replenishment", "FORECAST_TRIGGERED_REPLENISHMENT", {
                "medicine_id": data["medicine_id"],
                "medicine_name": data.get("medicine_name"),
                "store_id": data["store_id"],
                "predicted_demand": result["total_predicted"],
                "current_stock": current_stock,
                "shortfall": round(result["total_predicted"] - current_stock, 1),
                "confidence_score": result["confidence_score"],
                "explanation": result["explanation"],
            })
            logger.info(f"[AI AGENT] Replenishment triggered for {data.get('medicine_name')} at {data['store_id']}")

        db.commit()

        result["triggered_replenishment"] = triggered_replenishment
        if triggered_replenishment:
            result["replenishment_note"] = (
                f"Replenishment triggered: predicted demand ({result['total_predicted']}) "
                f"exceeds current stock ({current_stock})."
            )

        return jsonify(result)
    finally:
        db.close()


@app.route("/ai/forecasts", methods=["GET"])
@require_auth
def get_forecasts():
    """Retrieve stored forecast results."""
    db = SessionLocal()
    try:
        q = db.query(ForecastResult)
        medicine_id = request.args.get("medicine_id")
        store_id = request.args.get("store_id")
        if medicine_id:
            q = q.filter(ForecastResult.medicine_id == medicine_id)
        if store_id:
            q = q.filter(ForecastResult.store_id == store_id)
        forecasts = q.filter(
            ForecastResult.forecast_date >= date.today()
        ).order_by(ForecastResult.forecast_date.asc()).limit(100).all()
        return jsonify({"forecasts": [f.to_dict() for f in forecasts]})
    finally:
        db.close()


# ─── Anomaly Detection Agent ──────────────────────────────────────────────────

@app.route("/ai/anomalies/detect", methods=["POST"])
@require_role("admin", "supervisor", "pharmacist")
def detect_anomalies():
    """
    Run anomaly detection on sales data.

    Body:
    {
      "medicine_id": "...",
      "medicine_name": "...",
      "store_id": "...",
      "sales_history": [{"date": "...", "quantity": N}, ...]
    }
    """
    data = request.get_json()
    required = ["medicine_id", "store_id", "sales_history"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    anomalies = detect_sales_anomalies(
        medicine_id=data["medicine_id"],
        store_id=data["store_id"],
        medicine_name=data.get("medicine_name", "Unknown"),
        sales_history=data["sales_history"],
    )

    db = SessionLocal()
    try:
        saved = []
        for a in anomalies:
            log = AnomalyLog(
                anomaly_type=a["anomaly_type"],
                medicine_id=a["medicine_id"],
                store_id=a["store_id"],
                severity=a["severity"],
                description=a["description"],
                detected_value=a.get("detected_value"),
                expected_range=a.get("expected_range"),
            )
            db.add(log)
            saved.append(log)

        db.commit()

        # AI ACTION: publish alert for each anomaly → notification service reacts
        for log in saved:
            publish_event("notifications", "ANOMALY_DETECTED", {
                "anomaly_id": str(log.id),
                "anomaly_type": log.anomaly_type,
                "medicine_id": log.medicine_id,
                "store_id": log.store_id,
                "severity": log.severity,
                "description": log.description,
            })

        return jsonify({
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies,
            "message": f"Detected {len(anomalies)} anomalies. Alerts published." if anomalies else "No anomalies detected.",
        })
    finally:
        db.close()


@app.route("/ai/anomalies/stock-mismatch", methods=["POST"])
@require_role("admin", "supervisor")
def check_stock_mismatch():
    """
    Check for stock mismatch between system and physical count.

    Body:
    {
      "medicine_id": "...",
      "medicine_name": "...",
      "store_id": "...",
      "system_stock": 100,
      "physical_count": 85
    }
    """
    data = request.get_json()
    required = ["medicine_id", "store_id", "system_stock", "physical_count"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400

    anomaly = detect_stock_mismatch(
        medicine_id=data["medicine_id"],
        store_id=data["store_id"],
        medicine_name=data.get("medicine_name", "Unknown"),
        system_stock=int(data["system_stock"]),
        physical_count=int(data["physical_count"]),
    )

    if not anomaly:
        return jsonify({"mismatch_detected": False, "message": "Stock counts are within acceptable tolerance."})

    db = SessionLocal()
    try:
        log = AnomalyLog(
            anomaly_type=anomaly["anomaly_type"],
            medicine_id=anomaly["medicine_id"],
            store_id=anomaly["store_id"],
            severity=anomaly["severity"],
            description=anomaly["description"],
            detected_value=anomaly.get("detected_value"),
            expected_range=anomaly.get("expected_range"),
        )
        db.add(log)
        db.commit()

        publish_event("notifications", "ANOMALY_DETECTED", {
            "anomaly_id": str(log.id),
            **anomaly,
        })

        return jsonify({"mismatch_detected": True, "anomaly": anomaly})
    finally:
        db.close()


@app.route("/ai/anomalies", methods=["GET"])
@require_auth
def list_anomalies():
    """List stored anomaly logs."""
    db = SessionLocal()
    try:
        q = db.query(AnomalyLog)
        severity = request.args.get("severity")
        store_id = request.args.get("store_id")
        resolved = request.args.get("resolved", "false").lower() == "true"
        if severity:
            q = q.filter(AnomalyLog.severity == severity.upper())
        if store_id:
            q = q.filter(AnomalyLog.store_id == store_id)
        q = q.filter(AnomalyLog.is_resolved == resolved)
        logs = q.order_by(AnomalyLog.detected_at.desc()).limit(100).all()
        return jsonify({"anomalies": [l.to_dict() for l in logs]})
    finally:
        db.close()


@app.route("/ai/anomalies/<anomaly_id>/resolve", methods=["POST"])
@require_role("admin", "supervisor")
def resolve_anomaly(anomaly_id):
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        from datetime import datetime, timezone
        log = db.query(AnomalyLog).filter(AnomalyLog.id == anomaly_id).first()
        if not log:
            return jsonify({"error": "Anomaly not found"}), 404
        log.is_resolved = True
        log.resolution_notes = data.get("notes", "Resolved by supervisor")
        log.resolved_at = datetime.now(timezone.utc)
        db.commit()
        return jsonify({"message": "Anomaly resolved"})
    finally:
        db.close()


# ─── Conversational Agent ─────────────────────────────────────────────────────

@app.route("/ai/query", methods=["POST"])
@require_auth
def conversational_query():
    """
    Natural language query interface.

    Body: {"query": "What are the top selling medicines this week?"}
    Returns: SQL + explanation + (optionally) data if connected to DB
    """
    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Body must contain 'query' field"}), 400

    result = process_query(data["query"])

    if not result.get("matched"):
        return jsonify(result), 422

    return jsonify({
        "query": data["query"],
        "generated_sql": result.get("sql"),
        "explanation": result.get("explanation"),
        "target_db": result.get("db"),
        "method": result.get("method"),
        "note": "Execute the generated SQL against the target database to retrieve results.",
    })


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8006, debug=False)

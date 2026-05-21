"""
Demand Forecasting Agent.

Uses linear regression on historical sales data to predict
next 7-day demand per medicine per store.

Design:
- Input: list of (date, quantity_sold) data points
- Model: scikit-learn LinearRegression with day-of-week + trend features
- Output: 7-day forecast with confidence score and explanation
- Action: if forecast > current stock, triggers replenishment event
"""
import logging
from datetime import date, timedelta
from typing import List, Dict

import numpy as np

logger = logging.getLogger(__name__)


def _build_features(dates: List[date]) -> np.ndarray:
    """
    Feature engineering:
    - day_index: sequential day number (captures trend)
    - day_of_week: 0-6 (captures weekly seasonality)
    """
    base = dates[0]
    features = []
    for d in dates:
        day_index = (d - base).days
        dow = d.weekday()
        features.append([day_index, dow])
    return np.array(features)


def forecast_demand(
    medicine_id: str,
    outlet_id: str,
    medicine_name: str,
    sales_history: List[Dict],  # [{"date": "2024-01-01", "quantity": 15}, ...]
    forecast_days: int = 7,
) -> Dict:
    """
    Forecast demand for the next N days.

    Returns a dict with:
    - forecasts: list of {date, predicted_demand}
    - total_predicted: sum over forecast window
    - confidence_score: R² of the model (0-1)
    - explanation: human-readable reasoning
    - model_used: algorithm name
    """
    if len(sales_history) < 3:
        # Not enough data — fall back to simple average
        avg = sum(s["quantity"] for s in sales_history) / max(len(sales_history), 1)
        forecasts = []
        today = date.today()
        for i in range(1, forecast_days + 1):
            forecasts.append({
                "date": (today + timedelta(days=i)).isoformat(),
                "predicted_demand": round(avg, 1),
            })
        return {
            "medicine_id": medicine_id,
            "outlet_id": outlet_id,
            "medicine_name": medicine_name,
            "forecasts": forecasts,
            "total_predicted": round(avg * forecast_days, 1),
            "confidence_score": 0.5,
            "model_used": "simple_average_fallback",
            "explanation": (
                f"Insufficient history ({len(sales_history)} records). "
                f"Used average of {round(avg, 1)} units/day as baseline."
            ),
        }

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score

        # Parse and sort history
        history = sorted(sales_history, key=lambda x: x["date"])
        dates = [date.fromisoformat(h["date"]) for h in history]
        quantities = np.array([h["quantity"] for h in history], dtype=float)

        X = _build_features(dates)
        model = LinearRegression()
        model.fit(X, quantities)

        # Evaluate model quality
        y_pred_train = model.predict(X)
        r2 = r2_score(quantities, y_pred_train)
        confidence = max(0.0, min(1.0, r2))  # clamp to [0, 1]

        # Forecast future dates
        today = date.today()
        future_dates = [today + timedelta(days=i) for i in range(1, forecast_days + 1)]
        base_date = dates[0]

        future_features = []
        for d in future_dates:
            day_index = (d - base_date).days
            dow = d.weekday()
            future_features.append([day_index, dow])

        future_X = np.array(future_features)
        predictions = model.predict(future_X)
        predictions = np.maximum(predictions, 0)  # no negative demand

        forecasts = [
            {"date": d.isoformat(), "predicted_demand": round(float(p), 1)}
            for d, p in zip(future_dates, predictions)
        ]

        # Build explanation
        trend = model.coef_[0]
        trend_desc = "increasing" if trend > 0.5 else ("decreasing" if trend < -0.5 else "stable")
        avg_hist = round(float(np.mean(quantities)), 1)
        total_predicted = round(float(sum(predictions)), 1)

        explanation = (
            f"Based on {len(history)} days of sales history. "
            f"Average historical demand: {avg_hist} units/day. "
            f"Trend is {trend_desc} (slope={round(trend, 2)}). "
            f"Model confidence (R²): {round(confidence, 2)}. "
            f"Total predicted demand over {forecast_days} days: {total_predicted} units."
        )

        return {
            "medicine_id": medicine_id,
            "outlet_id": outlet_id,
            "medicine_name": medicine_name,
            "forecasts": forecasts,
            "total_predicted": total_predicted,
            "confidence_score": round(confidence, 3),
            "model_used": "linear_regression",
            "explanation": explanation,
        }

    except ImportError:
        logger.warning("scikit-learn not available, using moving average")
        # Fallback: 7-day moving average
        recent = [h["quantity"] for h in sales_history[-7:]]
        avg = sum(recent) / len(recent)
        today = date.today()
        forecasts = [
            {"date": (today + timedelta(days=i)).isoformat(), "predicted_demand": round(avg, 1)}
            for i in range(1, forecast_days + 1)
        ]
        return {
            "medicine_id": medicine_id,
            "outlet_id": outlet_id,
            "medicine_name": medicine_name,
            "forecasts": forecasts,
            "total_predicted": round(avg * forecast_days, 1),
            "confidence_score": 0.6,
            "model_used": "moving_average_7d",
            "explanation": f"7-day moving average: {round(avg, 1)} units/day.",
        }

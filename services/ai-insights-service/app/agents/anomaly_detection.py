"""
Anomaly Detection Agent.

Uses Isolation Forest (ML) with rule-based fallback to detect:
1. Unusual sales spikes (quantity >> historical average)
2. Stock mismatches (ledger vs physical count discrepancies)
3. Unusual return patterns

Design:
- Isolation Forest: unsupervised, no labeled data needed
- Rule-based: IQR method as fallback
- Output: anomaly score, severity, description, expected range
- Action: publishes ANOMALY_DETECTED event → notification service
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _iqr_bounds(values: List[float]):
    """Calculate IQR-based outlier bounds."""
    import statistics
    if len(values) < 4:
        return None, None
    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return lower, upper


def detect_sales_anomalies(
    medicine_id: str,
    outlet_id: str,
    medicine_name: str,
    sales_history: List[Dict],  # [{"date": "...", "quantity": N}]
) -> List[Dict]:
    """
    Detect anomalous sales quantities.
    Returns list of anomaly records (may be empty if all normal).
    """
    if len(sales_history) < 5:
        return []  # not enough data to detect anomalies

    quantities = [float(s["quantity"]) for s in sales_history]
    anomalies = []

    # Try Isolation Forest first
    try:
        from sklearn.ensemble import IsolationForest
        import numpy as np

        X = np.array(quantities).reshape(-1, 1)
        clf = IsolationForest(contamination=0.1, random_state=42)
        labels = clf.fit_predict(X)  # -1 = anomaly, 1 = normal
        scores = clf.score_samples(X)

        for i, (label, score) in enumerate(zip(labels, scores)):
            if label == -1:
                qty = quantities[i]
                avg = sum(quantities) / len(quantities)
                severity = "HIGH" if qty > avg * 3 else "MEDIUM"
                anomalies.append({
                    "anomaly_type": "SALES_SPIKE" if qty > avg else "SALES_DROP",
                    "medicine_id": medicine_id,
                    "outlet_id": outlet_id,
                    "severity": severity,
                    "description": (
                        f"Anomalous sales detected for {medicine_name} on {sales_history[i]['date']}. "
                        f"Quantity: {qty}, average: {round(avg, 1)}. "
                        f"Isolation Forest anomaly score: {round(score, 3)}."
                    ),
                    "detected_value": qty,
                    "expected_range": f"{round(avg * 0.5, 1)}-{round(avg * 1.5, 1)}",
                    "date": sales_history[i]["date"],
                    "model_used": "isolation_forest",
                })

    except ImportError:
        # Fallback: IQR method
        lower, upper = _iqr_bounds(quantities)
        if lower is None:
            return []
        avg = sum(quantities) / len(quantities)
        for i, qty in enumerate(quantities):
            if qty < lower or qty > upper:
                severity = "HIGH" if qty > avg * 3 else "MEDIUM"
                anomalies.append({
                    "anomaly_type": "SALES_SPIKE" if qty > upper else "SALES_DROP",
                    "medicine_id": medicine_id,
                    "outlet_id": outlet_id,
                    "severity": severity,
                    "description": (
                        f"Anomalous sales for {medicine_name} on {sales_history[i]['date']}. "
                        f"Quantity {qty} outside expected range [{round(lower,1)}, {round(upper,1)}]. "
                        f"Detected via IQR method."
                    ),
                    "detected_value": qty,
                    "expected_range": f"{round(lower, 1)}-{round(upper, 1)}",
                    "date": sales_history[i]["date"],
                    "model_used": "iqr_rule_based",
                })

    return anomalies


def detect_stock_mismatch(
    medicine_id: str,
    outlet_id: str,
    medicine_name: str,
    system_stock: int,
    physical_count: int,
    tolerance_pct: float = 0.05,
) -> Optional[Dict]:
    """
    Detect discrepancy between system stock and physical count.
    Flags if difference exceeds tolerance percentage.
    """
    if system_stock == 0 and physical_count == 0:
        return None

    diff = abs(system_stock - physical_count)
    base = max(system_stock, 1)
    diff_pct = diff / base

    if diff_pct <= tolerance_pct:
        return None  # within acceptable range

    severity = "CRITICAL" if diff_pct > 0.2 else ("HIGH" if diff_pct > 0.1 else "MEDIUM")

    return {
        "anomaly_type": "STOCK_MISMATCH",
        "medicine_id": medicine_id,
        "outlet_id": outlet_id,
        "severity": severity,
        "description": (
            f"Stock mismatch for {medicine_name} at outlet {outlet_id}. "
            f"System shows {system_stock} units, physical count is {physical_count}. "
            f"Discrepancy: {diff} units ({round(diff_pct * 100, 1)}%). "
            f"Possible causes: unrecorded sales, theft, or data entry error."
        ),
        "detected_value": float(diff),
        "expected_range": f"{round(system_stock * (1 - tolerance_pct))}-{round(system_stock * (1 + tolerance_pct))}",
        "model_used": "rule_based",
    }

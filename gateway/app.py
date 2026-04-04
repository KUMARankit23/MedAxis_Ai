"""
API Gateway — Central entry point for all MedAxis services.
Responsibilities:
  - Single public-facing URL (port 8000)
  - Route requests to appropriate microservices
  - Forward Authorization headers
  - Rate limiting (basic)
  - Request logging
  - Health aggregation
Port: 8000
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
import time
from collections import defaultdict

import requests
from flask import Flask, request, jsonify, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Service Registry ─────────────────────────────────────────────────────────
# Maps URL prefix → internal service URL
SERVICES = {
    "/auth":          os.getenv("AUTH_SERVICE_URL",          "http://localhost:8001"),
    "/inventory":     os.getenv("INVENTORY_SERVICE_URL",     "http://localhost:8002"),
    "/billing":       os.getenv("BILLING_SERVICE_URL",       "http://localhost:8003"),
    "/replenishment": os.getenv("REPLENISHMENT_SERVICE_URL", "http://localhost:8004"),
    "/reporting":     os.getenv("REPORTING_SERVICE_URL",     "http://localhost:8005"),
    "/ai":            os.getenv("AI_SERVICE_URL",            "http://localhost:8006"),
    "/notifications": os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8007"),
}

# ─── Basic Rate Limiter ───────────────────────────────────────────────────────
# Simple in-memory rate limiter: max 100 requests per minute per IP
_rate_store = defaultdict(list)
RATE_LIMIT = 100
RATE_WINDOW = 60  # seconds


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        return True
    _rate_store[ip].append(now)
    return False


# ─── Proxy Logic ─────────────────────────────────────────────────────────────

def proxy_request(target_url: str) -> Response:
    """Forward the incoming request to the target service."""
    # Forward headers (including Authorization)
    headers = {k: v for k, v in request.headers if k.lower() not in ("host", "content-length")}

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            timeout=10,
            allow_redirects=False,
        )
        # Return the upstream response as-is
        return Response(
            resp.content,
            status=resp.status_code,
            headers=dict(resp.headers),
        )
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Service unavailable", "target": target_url}), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Service timeout", "target": target_url}), 504


@app.before_request
def log_and_rate_limit():
    ip = request.remote_addr
    logger.info(f"[GATEWAY] {request.method} {request.path} from {ip}")
    if is_rate_limited(ip):
        return jsonify({"error": "Rate limit exceeded. Max 100 requests/minute."}), 429


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def gateway(path):
    full_path = f"/{path}"

    # Find matching service by longest prefix match
    matched_prefix = None
    for prefix in sorted(SERVICES.keys(), key=len, reverse=True):
        if full_path.startswith(prefix):
            matched_prefix = prefix
            break

    if not matched_prefix:
        return jsonify({"error": f"No service found for path: {full_path}"}), 404

    service_url = SERVICES[matched_prefix]
    target = f"{service_url}{full_path}"
    return proxy_request(target)


@app.route("/health")
def gateway_health():
    """Aggregate health check across all services."""
    results = {}
    for prefix, url in SERVICES.items():
        try:
            r = requests.get(f"{url}/health", timeout=3)
            results[prefix] = {"status": "ok", "code": r.status_code}
        except Exception as e:
            results[prefix] = {"status": "unreachable", "error": str(e)}

    all_ok = all(v["status"] == "ok" for v in results.values())
    return jsonify({
        "gateway": "ok",
        "services": results,
        "overall": "healthy" if all_ok else "degraded",
    }), 200 if all_ok else 207


@app.route("/")
def root():
    return jsonify({
        "platform": "MedAxis Platform",
        "version": "1.0.0",
        "services": list(SERVICES.keys()),
        "docs": "See /health for service status",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

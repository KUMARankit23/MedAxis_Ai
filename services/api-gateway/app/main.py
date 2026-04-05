"""
API Gateway — single entry point for all MedAxis services.

Responsibilities:
  - Route requests to the correct microservice by URL prefix
  - Rate limiting (100 req/min per IP, in-memory)
  - Forward Authorization headers transparently
  - Aggregate /health across all services
"""
import time
import logging
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.config import SERVICES, RATE_LIMIT, RATE_WINDOW

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app = FastAPI(
    title="MedAxis — API Gateway",
    description="Single entry point. Routes to auth, inventory, billing, replenishment, reporting, AI, notifications.",
    version="1.0.0",
)

# ── Rate limiter (in-memory, per IP) ─────────────────────────────────────────
_rate_store: dict = defaultdict(list)


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        return True
    _rate_store[ip].append(now)
    return False


# ── Proxy ─────────────────────────────────────────────────────────────────────

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    ip = request.client.host
    logger.info(f"[GATEWAY] {request.method} /{path} from {ip}")

    if is_rate_limited(ip):
        return JSONResponse({"error": "Rate limit exceeded. Max 100 req/min."}, status_code=429)

    full_path = f"/{path}"

    # Longest-prefix match
    matched = None
    for prefix in sorted(SERVICES.keys(), key=len, reverse=True):
        if full_path.startswith(prefix):
            matched = prefix
            break

    if not matched:
        return JSONResponse({"error": f"No service for path: {full_path}"}, status_code=404)

    target = f"{SERVICES[matched]}{full_path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(
                method=request.method, url=target,
                headers=headers, params=dict(request.query_params), content=body,
            )
        return Response(content=resp.content, status_code=resp.status_code,
                        headers=dict(resp.headers))
    except httpx.ConnectError:
        return JSONResponse({"error": "Service unavailable", "target": target}, status_code=503)
    except httpx.TimeoutException:
        return JSONResponse({"error": "Service timeout", "target": target}, status_code=504)


# ── Health aggregation ────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def gateway_health():
    results = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for prefix, url in SERVICES.items():
            try:
                r = await client.get(f"{url}/health")
                results[prefix] = {"status": "ok", "code": r.status_code}
            except Exception as e:
                results[prefix] = {"status": "unreachable", "error": str(e)}

    all_ok = all(v["status"] == "ok" for v in results.values())
    return JSONResponse(
        {"gateway": "ok", "services": results, "overall": "healthy" if all_ok else "degraded"},
        status_code=200 if all_ok else 207,
    )


@app.get("/", tags=["Info"])
async def root():
    return {
        "platform": "MedAxis Platform",
        "version": "1.0.0",
        "services": list(SERVICES.keys()),
        "docs": "Each service exposes /docs for Swagger UI",
    }

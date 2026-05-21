"""
API Gateway — single entry point for all MedAxis services.

Production hardening:
  - CORS restricted to ALLOWED_ORIGINS env var (no wildcard)
  - Redis-backed sliding-window rate limiting with Retry-After header
  - Correlation ID propagation
  - Circuit breaker (3 x 503 in 30s → open for 30s)
  - Request size limit (10 MB)
  - Structured JSON logging
  - Global exception handlers
"""
import sys
sys.path.insert(0, "/shared")

import time
import uuid
import json
import logging
import os
from collections import defaultdict
from datetime import datetime

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from medaxis_logging import setup_logging, get_logger, correlation_id_var
from config_validator import validate_all
from middleware import add_exception_handlers
from observability import setup_sentry, setup_metrics

from app.config import SERVICES, RATE_LIMIT, RATE_WINDOW

validate_all({
    "ALLOWED_ORIGINS": {"optional": True},
})

setup_logging("api-gateway")
logger = get_logger(__name__)
setup_sentry("api-gateway")

MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB

# ── Circuit breaker ───────────────────────────────────────────────────────────
_circuit: dict = defaultdict(lambda: {"failures": [], "open_until": 0.0})
CIRCUIT_THRESHOLD = 3
CIRCUIT_WINDOW    = 30
CIRCUIT_OPEN_TTL  = 30


def _circuit_is_open(prefix: str) -> bool:
    state = _circuit[prefix]
    now = time.time()
    if state["open_until"] > now:
        return True
    state["failures"] = [t for t in state["failures"] if t > now - CIRCUIT_WINDOW]
    return False


def _circuit_record_failure(prefix: str):
    now = time.time()
    state = _circuit[prefix]
    state["failures"].append(now)
    state["failures"] = [t for t in state["failures"] if t > now - CIRCUIT_WINDOW]
    if len(state["failures"]) >= CIRCUIT_THRESHOLD:
        state["open_until"] = now + CIRCUIT_OPEN_TTL
        logger.warning(f"Circuit breaker OPEN for prefix '{prefix}'")


def _circuit_record_success(prefix: str):
    _circuit[prefix]["failures"] = []
    _circuit[prefix]["open_until"] = 0.0


# ── Redis rate limiter (sliding window) ───────────────────────────────────────
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD") or None
            _redis = aioredis.Redis(
                host=redis_host, port=redis_port,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"Redis init failed: {e}")
    return _redis


async def is_rate_limited(ip: str) -> tuple[bool, int, int]:
    """
    Sliding window rate limiter using Redis sorted sets.
    Returns (is_limited, remaining, reset_ts).
    Falls back to allow-all if Redis is unavailable.
    """
    r = _get_redis()
    if r is None:
        return False, RATE_LIMIT, 0

    now = time.time()
    window_start = now - RATE_WINDOW
    key = f"ratelimit:{ip}"

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, RATE_WINDOW + 1)
        results = await pipe.execute()
        count = results[2]

        remaining = max(0, RATE_LIMIT - count)
        reset_ts = int(now + RATE_WINDOW)

        if count > RATE_LIMIT:
            return True, 0, reset_ts
        return False, remaining, reset_ts
    except Exception as e:
        logger.warning(f"Redis rate limit check failed: {e} — allowing request")
        return False, RATE_LIMIT, 0


# ── CORS ──────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else []

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MedAxis — API Gateway",
    description="Single entry point. Routes to auth, inventory, billing, replenishment, reporting, AI, notifications.",
    version="1.0.0",
)

add_exception_handlers(app)
setup_metrics(app, "api-gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next) -> Response:
    corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    correlation_id_var.set(corr_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response


# ── Gateway-local endpoints (must be registered BEFORE the catch-all proxy) ──

@app.get("/health", tags=["Health"])
async def gateway_health():
    results = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for prefix, url in SERVICES.items():
            try:
                r = await client.get(f"{url}/health")
                body = r.json()
                results[prefix] = {"status": body.get("status", "ok"), "code": r.status_code}
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
    }


# ── Proxy (catch-all — must be LAST) ─────────────────────────────────────────
_LOCAL_PATHS = {"/health", "/metrics", "/"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    start_time = time.time()
    ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    # Request size limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(
            {"error": "Request body too large. Maximum size is 10MB."},
            status_code=413,
            headers={"X-Correlation-ID": correlation_id},
        )

    # Redis-backed rate limiting
    limited, remaining, reset_ts = await is_rate_limited(ip)
    if limited:
        return JSONResponse(
            {"error": f"Rate limit exceeded. Max {RATE_LIMIT} req/{RATE_WINDOW}s."},
            status_code=429,
            headers={
                "X-Correlation-ID": correlation_id,
                "Retry-After": str(int(reset_ts - time.time())),
                "X-RateLimit-Limit": str(RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_ts),
            },
        )

    full_path = f"/{path}"
    matched = None
    for prefix in sorted(SERVICES.keys(), key=len, reverse=True):
        if full_path.startswith(prefix):
            matched = prefix
            break

    if not matched:
        return JSONResponse(
            {"error": f"No service for path: {full_path}"},
            status_code=404,
            headers={"X-Correlation-ID": correlation_id},
        )

    if _circuit_is_open(matched):
        return JSONResponse(
            {"error": "Service temporarily unavailable (circuit breaker open)", "path": full_path},
            status_code=503,
            headers={"X-Correlation-ID": correlation_id},
        )

    target = f"{SERVICES[matched]}{full_path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    headers["X-Correlation-ID"] = correlation_id
    headers["X-Forwarded-For"] = ip

    body = await request.body()
    if len(body) > MAX_BODY_SIZE:
        return JSONResponse(
            {"error": "Request body too large. Maximum size is 10MB."},
            status_code=413,
            headers={"X-Correlation-ID": correlation_id},
        )

    status_code = 500
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(
                method=request.method, url=target,
                headers=headers, params=dict(request.query_params), content=body,
            )
        status_code = resp.status_code

        if status_code == 503:
            _circuit_record_failure(matched)
        else:
            _circuit_record_success(matched)

        response_headers = dict(resp.headers)
        response_headers["X-Correlation-ID"] = correlation_id
        response_headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
        response_headers["X-RateLimit-Remaining"] = str(remaining)
        return Response(
            content=resp.content, status_code=resp.status_code,
            headers=response_headers,
        )

    except httpx.ConnectError:
        status_code = 503
        _circuit_record_failure(matched)
        return JSONResponse(
            {"error": "Service unavailable", "target": target},
            status_code=503,
            headers={"X-Correlation-ID": correlation_id},
        )
    except httpx.TimeoutException:
        status_code = 504
        return JSONResponse(
            {"error": "Service timeout", "target": target},
            status_code=504,
            headers={"X-Correlation-ID": correlation_id},
        )
    finally:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": full_path,
                "status": status_code,
                "duration_ms": duration_ms,
                "ip": ip,
            },
        )

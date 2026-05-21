"""Auth Service — JWT token creation, validation, and Redis blacklisting."""
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import redis.asyncio as aioredis

from app.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_HOURS

logger = logging.getLogger(__name__)

# ── Redis client for token blacklist ──────────────────────────────────────────
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.Redis(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"Redis init failed for JWT blacklist: {e}")
    return _redis


def create_access_token(user_id: str, username: str, role: str, outlet_id: Optional[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":       user_id,
        "username":  username,
        "role":      role,
        "outlet_id": outlet_id,
        "type":      "access",
        "jti":       str(uuid.uuid4()),   # unique token ID for blacklisting
        "iat":       now,
        "exp":       now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  user_id,
        "type": "refresh",
        "jti":  str(uuid.uuid4()),
        "iat":  now,
        "exp":  now + timedelta(hours=REFRESH_TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


async def blacklist_token(token: str) -> None:
    """Add a token's JTI to the Redis blacklist with TTL = remaining lifetime."""
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            return
        now = datetime.now(timezone.utc).timestamp()
        ttl = max(1, int(exp - now))
        r = _get_redis()
        if r:
            await r.setex(f"blacklist:jti:{jti}", ttl, "1")
            logger.info(f"Token blacklisted: jti={jti}, ttl={ttl}s")
    except Exception as e:
        logger.warning(f"Failed to blacklist token: {e}")


async def is_token_blacklisted(jti: str) -> bool:
    """Return True if the JTI is in the Redis blacklist. Fail-open if Redis unavailable."""
    try:
        r = _get_redis()
        if r:
            result = await r.get(f"blacklist:jti:{jti}")
            return result is not None
    except Exception as e:
        logger.warning(f"Redis blacklist check failed (fail-open): {e}")
    return False


async def verify_access_token(token: str) -> dict:
    """Decode, assert type is 'access', and check blacklist."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise jwt.InvalidTokenError("Token has been revoked")

    return payload

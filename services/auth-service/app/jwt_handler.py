"""Auth Service — JWT token creation and validation."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from app.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_HOURS


def create_access_token(user_id: str, username: str, role: str, outlet_id: Optional[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":       user_id,
        "username":  username,
        "role":      role,
        "outlet_id": outlet_id,
        "type":      "access",
        "iat":       now,
        "exp":       now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  user_id,
        "type": "refresh",
        "iat":  now,
        "exp":  now + timedelta(hours=REFRESH_TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def verify_access_token(token: str) -> dict:
    """Decode and assert token type is 'access'."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload

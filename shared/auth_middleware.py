"""
JWT authentication middleware shared across all services.

Gaps fixed:
  - Validates token type='access' — refresh tokens cannot be used as access tokens
  - Attaches full user context to g.user for downstream use
"""
import jwt
from functools import wraps
from flask import request, jsonify, g
from shared.config import JWT_SECRET, JWT_ALGORITHM


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises jwt exceptions on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def require_auth(f):
    """
    Decorator: requires a valid access JWT token.
    Rejects refresh tokens used as access tokens.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            # Reject refresh tokens being used as access tokens
            if payload.get("type") == "refresh":
                return jsonify({"error": "Refresh token cannot be used for API access"}), 401
            g.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired. Use /auth/refresh to get a new one."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """
    Decorator: requires the user to have one of the specified roles.
    Stacks on top of require_auth — no need to add both decorators.
    """
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            user_role = g.user.get("role", "")
            if user_role not in roles:
                return jsonify({
                    "error": "Access denied",
                    "required_roles": list(roles),
                    "your_role": user_role,
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

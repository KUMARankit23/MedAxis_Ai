"""
Auth Service — Entry point.
Handles: registration, login, token refresh, user management, audit logs.

Gaps fixed vs design document:
  - Access token: 15-min TTL (was 8-hr)
  - Refresh token: 8-hr TTL, separate /auth/refresh endpoint
  - Audit log: before/after state snapshots on mutations
  - /v1/ versioned routes (legacy unversioned routes kept for compatibility)
  - Token type validation (access vs refresh)
Port: 8001
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import json
import logging
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from flask import Flask, request, jsonify, g

from database import init_db, SessionLocal
from models import User, AuditLog, RoleEnum
from shared.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_HOURS
from shared.auth_middleware import require_auth, require_role
from shared.audit_logger import log_action

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Access token TTL: 15 minutes (matches document spec)
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))


# ─── Helpers ────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_tokens(user: User) -> dict:
    """
    Generate short-lived access token (15 min) + long-lived refresh token (8 hr).
    Access token carries full user claims for stateless auth.
    Refresh token carries only sub + type for rotation.
    """
    now = datetime.now(timezone.utc)

    access_payload = {
        "sub":      str(user.id),
        "username": user.username,
        "role":     user.role.value,
        "store_id": user.store_id,
        "type":     "access",
        "exp":      now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iat":      now,
    }
    refresh_payload = {
        "sub":  str(user.id),
        "type": "refresh",
        "exp":  now + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat":  now,
    }
    return {
        "access_token":       jwt.encode(access_payload,  JWT_SECRET, algorithm=JWT_ALGORITHM),
        "refresh_token":      jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM),
        "access_expires_in":  ACCESS_TOKEN_MINUTES * 60,   # seconds
        "refresh_expires_in": JWT_EXPIRY_HOURS * 3600,
        "token_type":         "Bearer",
    }


def record_audit(db, user_id, action, resource=None, before=None, after=None, status="SUCCESS", ip=None):
    """
    Persist audit entry with before/after state snapshots.
    before/after are dicts — stored as JSON for full mutation traceability.
    """
    details = {}
    if before is not None:
        details["before"] = before
    if after is not None:
        details["after"] = after

    log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        details=json.dumps(details) if details else None,
        ip_address=ip,
        status=status,
    )
    db.add(log)
    db.commit()


# ─── Health ──────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"service": "auth-service", "status": "ok"})


# ─── Auth Routes (/v1/ versioned + legacy) ───────────────────────────────────

@app.route("/v1/auth/register", methods=["POST"])
@app.route("/auth/register",    methods=["POST"])
@require_role("admin")
def register():
    """Create a new user. Admin only. Logs before/after state."""
    data = request.get_json()
    required = ["username", "email", "password", "role"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400

    if data["role"] not in [r.value for r in RoleEnum]:
        return jsonify({"error": f"Invalid role. Choose from: {[r.value for r in RoleEnum]}"}), 400

    db = SessionLocal()
    try:
        if db.query(User).filter(
            (User.username == data["username"]) | (User.email == data["email"])
        ).first():
            return jsonify({"error": "Username or email already exists"}), 409

        user = User(
            username=data["username"],
            email=data["email"],
            password_hash=hash_password(data["password"]),
            role=RoleEnum(data["role"]),
            store_id=data.get("store_id"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        after_state = user.to_dict()
        log_action(str(g.user["sub"]), g.user["role"], "USER_CREATE", str(user.id),
                   details={"after": after_state})
        record_audit(db, g.user["sub"], "USER_CREATE", str(user.id),
                     before=None, after=after_state)

        return jsonify({"message": "User created", "user": after_state}), 201
    finally:
        db.close()


@app.route("/v1/auth/login", methods=["POST"])
@app.route("/auth/login",    methods=["POST"])
def login():
    """
    Authenticate user. Returns access_token (15 min) + refresh_token (8 hr).
    Logs login success/failure with IP address.
    """
    data = request.get_json()
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "username and password required"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data["username"]).first()
        ip = request.remote_addr

        if not user or not check_password(data["password"], user.password_hash):
            if user:
                record_audit(db, user.id, "LOGIN", status="FAILURE", ip=ip)
            log_action(data["username"], "unknown", "LOGIN", "auth", status="FAILURE")
            return jsonify({"error": "Invalid credentials"}), 401

        if not user.is_active:
            record_audit(db, user.id, "LOGIN", status="FAILURE", ip=ip,
                         after={"reason": "account_disabled"})
            return jsonify({"error": "Account disabled"}), 403

        user.last_login = datetime.now(timezone.utc)
        db.commit()

        tokens = generate_tokens(user)
        record_audit(db, user.id, "LOGIN", ip=ip,
                     after={"role": user.role.value, "store_id": user.store_id})
        log_action(str(user.id), user.role.value, "LOGIN", "auth")

        return jsonify({**tokens, "user": user.to_dict()})
    finally:
        db.close()


@app.route("/v1/auth/refresh", methods=["POST"])
@app.route("/auth/refresh",    methods=["POST"])
def refresh_token():
    """
    Rotate access token using a valid refresh token.
    Refresh token must have type='refresh' claim.
    """
    data = request.get_json() or {}
    token = data.get("refresh_token") or request.headers.get("Authorization", "").split(" ", 1)[-1]

    if not token:
        return jsonify({"error": "refresh_token required"}), 400

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired. Please log in again."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    if payload.get("type") != "refresh":
        return jsonify({"error": "Token is not a refresh token"}), 400

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user or not user.is_active:
            return jsonify({"error": "User not found or disabled"}), 401

        tokens = generate_tokens(user)
        return jsonify({**tokens, "user": user.to_dict()})
    finally:
        db.close()


@app.route("/v1/auth/me", methods=["GET"])
@app.route("/auth/me",    methods=["GET"])
@require_auth
def me():
    return jsonify({"user": g.user})


@app.route("/v1/auth/users", methods=["GET"])
@app.route("/auth/users",    methods=["GET"])
@require_role("admin", "supervisor")
def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return jsonify({"users": [u.to_dict() for u in users]})
    finally:
        db.close()


@app.route("/v1/auth/users/<user_id>/deactivate", methods=["POST"])
@app.route("/auth/users/<user_id>/deactivate",    methods=["POST"])
@require_role("admin")
def deactivate_user(user_id):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        before_state = user.to_dict()
        user.is_active = False
        db.commit()
        after_state = user.to_dict()

        log_action(str(g.user["sub"]), g.user["role"], "USER_DEACTIVATE", user_id,
                   details={"before": before_state, "after": after_state})
        record_audit(db, g.user["sub"], "USER_DEACTIVATE", user_id,
                     before=before_state, after=after_state)
        return jsonify({"message": "User deactivated"})
    finally:
        db.close()


@app.route("/v1/auth/audit-logs", methods=["GET"])
@app.route("/auth/audit-logs",    methods=["GET"])
@require_role("admin")
def audit_logs():
    """
    Searchable audit log. Supports filtering by action, user_id, status.
    Returns before/after state snapshots for full mutation traceability.
    """
    db = SessionLocal()
    try:
        q = db.query(AuditLog).order_by(AuditLog.timestamp.desc())

        # Optional filters
        action_filter = request.args.get("action")
        user_filter   = request.args.get("user_id")
        status_filter = request.args.get("status")
        if action_filter:
            q = q.filter(AuditLog.action == action_filter.upper())
        if user_filter:
            q = q.filter(AuditLog.user_id == user_filter)
        if status_filter:
            q = q.filter(AuditLog.status == status_filter.upper())

        logs = q.limit(200).all()
        return jsonify({"logs": [
            {
                "id":         str(l.id),
                "user_id":    str(l.user_id) if l.user_id else None,
                "action":     l.action,
                "resource":   l.resource,
                "status":     l.status,
                "ip_address": l.ip_address,
                "details":    json.loads(l.details) if l.details else {},
                "timestamp":  l.timestamp.isoformat(),
            } for l in logs
        ]})
    finally:
        db.close()


# ─── Bootstrap ──────────────────────────────────────────────────────────────

def seed_admin():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "admin").first():
            admin = User(
                username="admin",
                email="admin@medaxis.com",
                password_hash=hash_password("Admin@123"),
                role=RoleEnum.admin,
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin created: admin / Admin@123")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    seed_admin()
    app.run(host="0.0.0.0", port=8001, debug=False)

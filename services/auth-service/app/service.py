"""Auth Service — business logic layer (separated from routes)."""
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, AuditLog, RoleEnum
from app.schemas import CreateUserRequest
from app.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.config import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_HOURS

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

PASSWORD_POLICY_RE = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]).{8,}$'
)


def validate_password_policy(password: str) -> None:
    """Raise ValueError if password does not meet policy requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>/?\\|`~]', password):
        raise ValueError("Password must contain at least one special character")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def _write_audit(
    db: AsyncSession, user_id, action: str,
    resource: str = None, before: dict = None,
    after: dict = None, status: str = "SUCCESS", ip: str = None
):
    import uuid
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            pass
    log = AuditLog(
        user_id=user_id, action=action, resource=resource,
        before_state=json.dumps(before) if before else None,
        after_state=json.dumps(after) if after else None,
        ip_address=ip, status=status,
    )
    db.add(log)
    await db.commit()


async def login(db: AsyncSession, username: str, password: str, ip: str):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= LOCKOUT_MAX_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            await db.commit()
            await _write_audit(db, user.id, "LOGIN", status="FAILURE", ip=ip)
        raise ValueError("Invalid credentials")

    if not user.is_active:
        await _write_audit(db, user.id, "LOGIN", status="FAILURE", ip=ip,
                           after={"reason": "account_disabled"})
        raise PermissionError("Account disabled")

    # Check lockout
    now = datetime.now(timezone.utc)
    if user.locked_until and now < user.locked_until:
        remaining = int((user.locked_until - now).total_seconds() / 60) + 1
        raise PermissionError(f"Account locked. Try again in {remaining} minute(s).")

    # Successful login — reset lockout counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now
    await db.commit()

    access  = create_access_token(str(user.id), user.username, user.role.value, user.outlet_id)
    refresh = create_refresh_token(str(user.id))

    await _write_audit(db, user.id, "LOGIN", ip=ip,
                       after={"role": user.role.value, "outlet_id": user.outlet_id})
    return access, refresh, user


async def refresh(db: AsyncSession, refresh_token: str):
    import jwt as pyjwt
    import uuid
    try:
        payload = decode_token(refresh_token)
    except pyjwt.ExpiredSignatureError:
        raise ValueError("Refresh token expired")
    except pyjwt.InvalidTokenError:
        raise ValueError("Invalid token")

    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    user_id = payload["sub"]
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            pass

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise ValueError("User not found or disabled")

    access  = create_access_token(str(user.id), user.username, user.role.value, user.outlet_id)
    new_ref = create_refresh_token(str(user.id))
    return access, new_ref, user


async def create_user(db: AsyncSession, data: CreateUserRequest, actor_id: str, actor_role: str):
    result = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if result.scalar_one_or_none():
        raise ValueError("Username or email already exists")

    # Password policy validation
    validate_password_policy(data.password)

    user = User(
        username=data.username, email=data.email,
        password_hash=hash_password(data.password),
        role=RoleEnum(data.role), outlet_id=data.outlet_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await _write_audit(db, actor_id, "USER_CREATE", str(user.id),
                       after={"username": user.username, "role": user.role.value})
    return user


async def deactivate_user(db: AsyncSession, user_id: str, actor_id: str):
    import uuid
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            pass
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise LookupError("User not found")

    before = {"is_active": user.is_active}
    user.is_active = False
    await db.commit()

    await _write_audit(db, actor_id, "USER_DEACTIVATE", str(user.id),
                       before=before, after={"is_active": False})
    return user


async def seed_admin(db: AsyncSession):
    result = await db.execute(select(User).where(User.username == "admin"))
    if not result.scalar_one_or_none():
        admin = User(
            username="admin", email="admin@medaxis.com",
            password_hash=hash_password("Admin@123"),
            role=RoleEnum.admin,
        )
        db.add(admin)
        await db.commit()


async def unlock_user(db: AsyncSession, user_id: str, actor_id: str):
    import uuid
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            pass
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise LookupError("User not found")

    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    await _write_audit(db, actor_id, "USER_UNLOCK", str(user.id),
                       after={"unlocked_by": actor_id})
    return user

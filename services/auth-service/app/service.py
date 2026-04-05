"""Auth Service — business logic layer (separated from routes)."""
import json
from datetime import datetime, timezone
from typing import Optional
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, AuditLog, RoleEnum
from app.schemas import CreateUserRequest
from app.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.config import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_HOURS


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def _write_audit(
    db: AsyncSession, user_id, action: str,
    resource: str = None, before: dict = None,
    after: dict = None, status: str = "SUCCESS", ip: str = None
):
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
            await _write_audit(db, user.id, "LOGIN", status="FAILURE", ip=ip)
        raise ValueError("Invalid credentials")

    if not user.is_active:
        await _write_audit(db, user.id, "LOGIN", status="FAILURE", ip=ip,
                           after={"reason": "account_disabled"})
        raise PermissionError("Account disabled")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access  = create_access_token(str(user.id), user.username, user.role.value, user.outlet_id)
    refresh = create_refresh_token(str(user.id))

    await _write_audit(db, user.id, "LOGIN", ip=ip,
                       after={"role": user.role.value, "outlet_id": user.outlet_id})
    return access, refresh, user


async def refresh(db: AsyncSession, refresh_token: str):
    import jwt as pyjwt
    try:
        payload = decode_token(refresh_token)
    except pyjwt.ExpiredSignatureError:
        raise ValueError("Refresh token expired")
    except pyjwt.InvalidTokenError:
        raise ValueError("Invalid token")

    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
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
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise LookupError("User not found")

    before = {"is_active": user.is_active}
    user.is_active = False
    await db.commit()

    await _write_audit(db, actor_id, "USER_DEACTIVATE", user_id,
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

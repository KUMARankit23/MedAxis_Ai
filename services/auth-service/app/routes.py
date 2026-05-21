"""Auth Service — FastAPI route definitions."""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import (
    LoginRequest, RefreshRequest, CreateUserRequest,
    TokenResponse, UserResponse, AuditLogResponse,
)
from app.jwt_handler import verify_access_token, blacklist_token
from app.service import login, refresh, create_user, deactivate_user, unlock_user
from app.config import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_HOURS

router = APIRouter()


# ── Pydantic schemas for previously untyped endpoints ────────────────────────

class ChangePasswordRequest(BaseModel):
    new_password: str

    model_config = {"str_strip_whitespace": True}


# ── Dependency: get current user from Bearer token ────────────────────────────

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    try:
        return await verify_access_token(auth.split(" ", 1)[1])
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


def require_role(*roles):
    async def dep(user: dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {list(roles)}"
            )
        return user
    return dep


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login_route(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    try:
        access, refresh_tok, user = await login(db, body.username, body.password, client_ip)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return TokenResponse(
        access_token=access, refresh_token=refresh_tok,
        access_expires_in=ACCESS_TOKEN_MINUTES * 60,
        refresh_expires_in=REFRESH_TOKEN_HOURS * 3600,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_route(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        access, new_ref, user = await refresh(db, body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return TokenResponse(
        access_token=access, refresh_token=new_ref,
        access_expires_in=ACCESS_TOKEN_MINUTES * 60,
        refresh_expires_in=REFRESH_TOKEN_HOURS * 3600,
        user=UserResponse.model_validate(user),
    )


@router.post("/auth/verify", tags=["Auth (Internal)"])
async def verify_token(request: Request):
    """Internal endpoint — called by API gateway to validate tokens."""
    user = await get_current_user(request)
    return user


@router.get("/auth/me", response_model=UserResponse, tags=["Auth"])
async def me(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import uuid
    user_id = user["sub"]
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            pass
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(u)


@router.post("/auth/users", response_model=UserResponse, status_code=201, tags=["Users"])
async def create_user_route(
    body: CreateUserRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await create_user(db, body, actor["sub"], actor["role"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserResponse.model_validate(user)


@router.get("/auth/users", response_model=List[UserResponse], tags=["Users"])
async def list_users(
    actor: dict = Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/auth/users/{user_id}/deactivate", response_model=UserResponse, tags=["Users"])
async def deactivate(
    user_id: str,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await deactivate_user(db, user_id, actor["sub"])
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return UserResponse.model_validate(user)


@router.post("/auth/users/{user_id}/unlock", response_model=UserResponse, tags=["Users"])
async def unlock(
    user_id: str,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await unlock_user(db, user_id, actor["sub"])
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return UserResponse.model_validate(user)


@router.post("/auth/logout", tags=["Auth"])
async def logout(request: Request, user: dict = Depends(get_current_user)):
    """Server-side logout — blacklists the access token in Redis."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        await blacklist_token(token)
    return {"message": "Logged out successfully. Token has been invalidated."}


@router.post("/auth/users/{user_id}/change-password", tags=["Users"])
async def change_password(
    user_id: str,
    body: ChangePasswordRequest,
    actor: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admins can change any user's password. Users can change their own."""
    if actor["sub"] != user_id and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only change your own password")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="new_password must be at least 8 characters")

    import uuid
    target_user_id = user_id
    if isinstance(target_user_id, str):
        try:
            target_user_id = uuid.UUID(target_user_id)
        except ValueError:
            pass

    result = await db.execute(select(User).where(User.id == target_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from app.service import hash_password, validate_password_policy
    validate_password_policy(body.new_password)
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}


@router.get("/auth/audit-logs", response_model=List[AuditLogResponse], tags=["Audit"])
async def audit_logs(
    action: Optional[str] = None,
    status: Optional[str] = None,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200)
    if action:
        q = q.where(AuditLog.action == action.upper())
    if status:
        q = q.where(AuditLog.status == status.upper())
    result = await db.execute(q)
    return [AuditLogResponse.model_validate(l) for l in result.scalars().all()]

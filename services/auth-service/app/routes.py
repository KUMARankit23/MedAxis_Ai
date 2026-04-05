"""Auth Service — FastAPI route definitions."""
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models import User, AuditLog
from app.schemas import (
    LoginRequest, RefreshRequest, CreateUserRequest,
    TokenResponse, UserResponse, AuditLogResponse
)
from app.jwt_handler import verify_access_token
from app.service import login, refresh, create_user, deactivate_user
from app.config import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_HOURS

router = APIRouter()


# ── Dependency: get current user from Bearer token ────────────────────────────

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    try:
        return verify_access_token(auth.split(" ", 1)[1])
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
    try:
        access, refresh_tok, user = await login(db, body.username, body.password, request.client.host)
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
    result = await db.execute(select(User).where(User.id == user["sub"]))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(u)


@router.post("/auth/users", response_model=UserResponse, status_code=201, tags=["Users"])
async def create_user_route(
    body: CreateUserRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    try:
        user = await create_user(db, body, actor["sub"], actor["role"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserResponse.model_validate(user)


@router.get("/auth/users", response_model=List[UserResponse], tags=["Users"])
async def list_users(
    actor: dict = Depends(require_role("admin", "supervisor")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]


@router.post("/auth/users/{user_id}/deactivate", response_model=UserResponse, tags=["Users"])
async def deactivate(
    user_id: str,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    try:
        user = await deactivate_user(db, user_id, actor["sub"])
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return UserResponse.model_validate(user)


@router.get("/auth/audit-logs", response_model=List[AuditLogResponse], tags=["Audit"])
async def audit_logs(
    action: str = None, status: str = None,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db)
):
    q = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200)
    if action:
        q = q.where(AuditLog.action == action.upper())
    if status:
        q = q.where(AuditLog.status == status.upper())
    result = await db.execute(q)
    return [AuditLogResponse.model_validate(l) for l in result.scalars().all()]

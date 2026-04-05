"""Auth Service — Pydantic request/response schemas."""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models import RoleEnum


# ── Request schemas ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CreateUserRequest(BaseModel):
    username:  str
    email:     EmailStr
    password:  str
    role:      RoleEnum
    outlet_id: Optional[str] = None


# ── Response schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id:        UUID
    username:  str
    email:     str
    role:      RoleEnum
    outlet_id: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token:       str
    refresh_token:      str
    token_type:         str = "Bearer"
    access_expires_in:  int   # seconds
    refresh_expires_in: int
    user:               UserResponse


class AuditLogResponse(BaseModel):
    id:           UUID
    user_id:      Optional[UUID]
    action:       str
    resource:     Optional[str]
    before_state: Optional[str]
    after_state:  Optional[str]
    ip_address:   Optional[str]
    status:       str
    timestamp:    datetime

    class Config:
        from_attributes = True

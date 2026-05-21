"""Auth Service — SQLAlchemy ORM models."""
import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class RoleEnum(str, enum.Enum):
    admin               = "admin"
    pharmacist          = "pharmacist"
    supervisor          = "supervisor"
    inventory_planner   = "inventory_planner"


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    email         = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role          = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.pharmacist)
    outlet_id     = Column(String(50), nullable=True)
    is_active              = Column(Boolean, default=True)
    created_at             = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login             = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts  = Column(Integer, default=0, nullable=False)
    locked_until           = Column(DateTime(timezone=True), nullable=True)

    audit_logs = relationship("AuditLog", back_populates="user", lazy="select")


class AuditLog(Base):
    """Append-only compliance trail — no UPDATE or DELETE allowed."""
    __tablename__ = "audit_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action      = Column(String(100), nullable=False)
    resource    = Column(String(200), nullable=True)
    before_state = Column(Text, nullable=True)   # JSON snapshot
    after_state  = Column(Text, nullable=True)   # JSON snapshot
    ip_address  = Column(String(50), nullable=True)
    status      = Column(String(20), default="SUCCESS")
    timestamp   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User", back_populates="audit_logs")

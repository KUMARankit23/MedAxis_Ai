"""
Auth Service — Database models.
Owns: users, roles, audit_logs tables.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
from shared.compat import GUID
import uuid
import enum

Base = declarative_base()


class RoleEnum(str, enum.Enum):
    admin = "admin"
    pharmacist = "pharmacist"
    supervisor = "supervisor"


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.pharmacist)
    store_id = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    audit_logs = relationship("AuditLog", back_populates="user", lazy="dynamic")

    def to_dict(self):
        return {
            "id": str(self.id),
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "store_id": self.store_id,
            "is_active": self.is_active,
        }


class AuditLog(Base):
    """Immutable audit trail for compliance."""
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(200), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    status = Column(String(20), default="SUCCESS")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="audit_logs")

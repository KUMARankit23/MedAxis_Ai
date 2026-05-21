"""Notification Service — event-driven alerts."""
import sys
import uuid
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, Text, Boolean, select, text
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel
from typing import Optional

sys.path.insert(0, "/shared")

from medaxis_logging import setup_logging, get_logger
from config_validator import validate_all
from middleware import add_middleware, add_exception_handlers
from observability import setup_sentry, setup_metrics

from app.config import DATABASE_URL

validate_all({
    "DATABASE_URL": {"min_length": 10},
})

setup_logging("notification-service")
logger = get_logger(__name__)
setup_sentry("notification-service")

ASYNC_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(
    ASYNC_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession,
    autocommit=False, autoflush=False, expire_on_commit=False,
)
Base = declarative_base()


class Notification(Base):
    __tablename__ = "notifications"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_type = Column(String(100), nullable=False)
    channel           = Column(String(50), default="LOG")
    recipient         = Column(String(200))
    subject           = Column(String(300))
    message           = Column(Text, nullable=False)
    source_service    = Column(String(100))
    is_sent           = Column(Boolean, default=True)
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Notification service starting — initialising database")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Notification service ready")
    yield


app = FastAPI(
    title="MedAxis — Notification Service",
    description="Event-driven alerts for low stock, anomalies, and replenishment approvals.",
    version="1.0.0",
    lifespan=lifespan,
)

add_middleware(app, "notification-service")
add_exception_handlers(app)
setup_metrics(app, "notification-service")


class NotificationCreate(BaseModel):
    notification_type: str
    message: str
    subject: Optional[str] = None
    recipient: Optional[str] = None
    channel: str = "LOG"
    source_service: Optional[str] = None


@app.get("/health", tags=["Health"])
async def health():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"service": "notification-service", "status": "ok", "checks": {"database": "ok"}}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"service": "notification-service", "status": "degraded", "checks": {"database": "error"}},
        )


@app.post("/notifications", status_code=201, tags=["Notifications"])
async def create_notification(body: NotificationCreate):
    async with AsyncSessionLocal() as db:
        notif = Notification(
            notification_type=body.notification_type.upper(),
            channel=body.channel.upper(),
            recipient=body.recipient,
            subject=body.subject or body.notification_type,
            message=body.message,
            source_service=body.source_service,
            is_sent=True,
        )
        db.add(notif)
        await db.commit()
        logger.info(f"Notification sent: {body.notification_type}: {body.message[:80]}")
        return {
            "id": str(notif.id),
            "notification_type": notif.notification_type,
            "message": notif.message,
            "created_at": notif.created_at.isoformat(),
        }


@app.get("/notifications", tags=["Notifications"])
async def list_notifications(
    notification_type: Optional[str] = None,
    limit: int = 50,
):
    async with AsyncSessionLocal() as db:
        q = select(Notification).order_by(Notification.created_at.desc()).limit(min(limit, 200))
        if notification_type:
            q = q.where(Notification.notification_type == notification_type.upper())
        result = await db.execute(q)
        return [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "subject": n.subject,
                "message": n.message,
                "source_service": n.source_service,
                "channel": n.channel,
                "is_sent": n.is_sent,
                "created_at": n.created_at.isoformat(),
            }
            for n in result.scalars().all()
        ]

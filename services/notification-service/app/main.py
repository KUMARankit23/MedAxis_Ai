"""Notification Service — event-driven alerts."""
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.config import DATABASE_URL

ASYNC_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(ASYNC_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession,
                                  autocommit=False, autoflush=False, expire_on_commit=False)
Base = declarative_base()


class Notification(Base):
    __tablename__ = "notifications"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_type = Column(String(100), nullable=False)
    channel           = Column(String(50), default="LOG")
    recipient         = Column(String(200))
    subject           = Column(String(300))
    message           = Column(Text, nullable=False)
    is_sent           = Column(Boolean, default=True)
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="MedAxis — Notification Service",
    description="Event-driven alerts for low stock, anomalies, and replenishment approvals.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
async def health():
    return {"service": "notification-service", "status": "ok"}


@app.get("/notifications", tags=["Notifications"])
async def list_notifications():
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(Notification).order_by(Notification.created_at.desc()).limit(50)
        )
        return [
            {"id": str(n.id), "type": n.notification_type, "subject": n.subject,
             "message": n.message, "is_sent": n.is_sent, "created_at": n.created_at.isoformat()}
            for n in result.scalars().all()
        ]

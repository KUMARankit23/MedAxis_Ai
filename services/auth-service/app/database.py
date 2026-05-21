"""Auth Service — async SQLAlchemy database session with connection pooling."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

ASYNC_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# SQLite (used in tests) does not support connection pool arguments
_is_sqlite = ASYNC_URL.startswith("sqlite")
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": not _is_sqlite}
if not _is_sqlite:
    _engine_kwargs.update(
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
    )

engine = create_async_engine(ASYNC_URL, **_engine_kwargs)

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession,
    autocommit=False, autoflush=False, expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

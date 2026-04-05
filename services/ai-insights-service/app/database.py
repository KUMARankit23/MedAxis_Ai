from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL
ASYNC_URL = DATABASE_URL.replace("postgresql://","postgresql+asyncpg://")
engine = create_async_engine(ASYNC_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False)
Base = declarative_base()
async def get_db():
    async with AsyncSessionLocal() as s: yield s
async def init_db():
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)

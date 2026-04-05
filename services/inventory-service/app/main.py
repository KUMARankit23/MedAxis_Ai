from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import init_db
from app.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="MedAxis — Inventory Service",
              description="Stock management, batch/expiry tracking, FEFO deduction, ledger.",
              version="1.0.0", lifespan=lifespan)
app.include_router(router)

@app.get("/health", tags=["Health"])
async def health():
    return {"service": "inventory-service", "status": "ok"}

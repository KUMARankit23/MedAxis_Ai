from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import init_db
from app.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(); yield

app = FastAPI(title="MedAxis — Billing Service",
              description="Prescriptions, OTC/Rx invoicing, GST calculation, stock deduction.",
              version="1.0.0", lifespan=lifespan)
app.include_router(router)

@app.get("/health", tags=["Health"])
async def health(): return {"service": "billing-service", "status": "ok"}

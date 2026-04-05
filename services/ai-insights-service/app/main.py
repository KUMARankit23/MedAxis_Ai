from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import init_db
from app.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(); yield

app = FastAPI(title="MedAxis — AI Insights Service",
              description="Demand forecasting, anomaly detection, and conversational NL query agents.",
              version="1.0.0", lifespan=lifespan)
app.include_router(router)

@app.get("/health", tags=["Health"])
async def health(): return {"service": "ai-insights-service", "status": "ok"}

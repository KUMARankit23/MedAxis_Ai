from fastapi import FastAPI
from app.routes import router

app = FastAPI(title="MedAxis — Reporting Service",
              description="BI dashboards, sales analytics, store performance, inventory reports.",
              version="1.0.0")
app.include_router(router)

@app.get("/health", tags=["Health"])
async def health(): return {"service": "reporting-service", "status": "ok"}

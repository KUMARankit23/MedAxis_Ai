# Setup Guide

## Option 1 — Docker Compose (Recommended)

```bash
# 1. Clone and configure
git clone https://github.com/KUMARankit23/MedAxis_Case_Study_Centific.git
cd MedAxis_Case_Study_Centific
cp .env.example .env
# Edit .env — set DB_PASSWORD and JWT_SECRET

# 2. Start all services
docker compose up -d --build

# 3. Seed demo data
python init-db/02_seed_data.py

# 4. Open Swagger UI
# http://localhost:8001/docs  (auth)
# http://localhost:8002/docs  (inventory)
# http://localhost:8003/docs  (billing)
# http://localhost:8005/docs  (reporting)
# http://localhost:8006/docs  (AI insights)
```

---

## Option 2 — Local (PostgreSQL already installed)

### Prerequisites
- Python 3.12
- PostgreSQL 15+
- `pip install fastapi uvicorn sqlalchemy asyncpg pyjwt bcrypt pydantic httpx scikit-learn numpy`

### Setup

```bash
# 1. Create databases
psql -U postgres -f init-db/01_create_databases.sql

# 2. Set environment variables
set DB_HOST=localhost
set DB_PASSWORD=yourpassword
set JWT_SECRET=your-secret-key

# 3. Start each service (separate terminals)
cd services/auth-service        && uvicorn app.main:app --port 8001 --reload
cd services/inventory-service   && uvicorn app.main:app --port 8002 --reload
cd services/billing-service     && uvicorn app.main:app --port 8003 --reload
cd services/replenishment-service && uvicorn app.main:app --port 8004 --reload
cd services/reporting-service   && uvicorn app.main:app --port 8005 --reload
cd services/ai-insights-service && uvicorn app.main:app --port 8006 --reload
cd services/notification-service && uvicorn app.main:app --port 8007 --reload
cd services/api-gateway         && uvicorn app.main:app --port 8000 --reload

# 4. Seed data
python init-db/02_seed_data.py
```

---

## Default Credentials

| Username | Password | Role |
|---|---|---|
| admin | Admin@123 | admin |
| pharmacist1 | Pharma@123 | pharmacist |
| supervisor1 | Super@123 | supervisor |
| planner1 | Plan@123 | inventory_planner |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_USER` | postgres | PostgreSQL user |
| `DB_PASSWORD` | postgres | PostgreSQL password |
| `JWT_SECRET` | (required) | JWT signing secret |
| `ACCESS_TOKEN_MINUTES` | 15 | Access token TTL |
| `REFRESH_TOKEN_HOURS` | 8 | Refresh token TTL |
| `OPENAI_API_KEY` | (optional) | For NL query agent |
| `GROQ_API_KEY` | (optional) | Alternative to OpenAI |
| `AI_PROVIDER` | pattern | `pattern` \| `openai` \| `groq` |

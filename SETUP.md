# MedAxis Platform — Setup Guide

## Quick Start (Docker — Recommended)

```bash
# 1. Copy environment config
cp .env.example .env
# Edit .env — change DB_PASSWORD and JWT_SECRET at minimum

# 2. Build and start all services
docker compose up -d --build

# 3. Wait ~30s for services to be healthy, then seed demo data
python init-db/02_seed_data.py

# 4. Open the app
#    Frontend:  http://localhost:3000
#    Gateway:   http://localhost:8000
```

### Default Credentials

| Username      | Password     | Role              | Access |
|---------------|--------------|-------------------|--------|
| admin         | Admin@123    | admin             | Full access |
| pharmacist1   | Pharma@123   | pharmacist        | Billing, Inventory |
| supervisor1   | Super@123    | supervisor        | Analytics, Replenishment |
| planner1      | Plan@123     | inventory_planner | Inventory, Replenishment |

---

## Service URLs

| Service            | Port | Swagger UI |
|--------------------|------|------------|
| Frontend           | 3000 | — |
| API Gateway        | 8000 | http://localhost:8000/docs |
| Auth Service       | 8001 | http://localhost:8001/docs |
| Inventory Service  | 8002 | http://localhost:8002/docs |
| Billing Service    | 8003 | http://localhost:8003/docs |
| Replenishment      | 8004 | http://localhost:8004/docs |
| Reporting Service  | 8005 | http://localhost:8005/docs |
| AI Insights        | 8006 | http://localhost:8006/docs |
| Notification       | 8007 | http://localhost:8007/docs |

---

## Local Development (without Docker)

### Prerequisites
- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Node.js 20+

### Backend

```bash
# 1. Create all databases
psql -U postgres -f init-db/01_create_databases.sql

# 2. Set environment variables (Windows)
set DB_HOST=localhost
set DB_PASSWORD=postgres
set JWT_SECRET=your-secret-key
set REDIS_HOST=localhost

# 3. Install dependencies and start each service (separate terminals)
cd services/auth-service        && pip install -r requirements.txt && uvicorn app.main:app --port 8001 --reload
cd services/inventory-service   && pip install -r requirements.txt && uvicorn app.main:app --port 8002 --reload
cd services/billing-service     && pip install -r requirements.txt && uvicorn app.main:app --port 8003 --reload
cd services/replenishment-service && pip install -r requirements.txt && uvicorn app.main:app --port 8004 --reload
cd services/reporting-service   && pip install -r requirements.txt && uvicorn app.main:app --port 8005 --reload
cd services/ai-insights-service && pip install -r requirements.txt && uvicorn app.main:app --port 8006 --reload
cd services/notification-service && pip install -r requirements.txt && uvicorn app.main:app --port 8007 --reload
cd services/api-gateway         && pip install -r requirements.txt && uvicorn app.main:app --port 8000 --reload

# 4. Seed data
python init-db/02_seed_data.py
```

### Frontend

```bash
cd frontend
npm install
npm start
# Opens at http://localhost:3000
# Proxies API calls to http://localhost:8000
```

---

## Environment Variables

| Variable                   | Default                          | Description |
|----------------------------|----------------------------------|-------------|
| `DB_HOST`                  | localhost                        | PostgreSQL host |
| `DB_PORT`                  | 5432                             | PostgreSQL port |
| `DB_USER`                  | postgres                         | PostgreSQL user |
| `DB_PASSWORD`              | postgres                         | PostgreSQL password — **change in production** |
| `REDIS_HOST`               | localhost                        | Redis host |
| `REDIS_PORT`               | 6379                             | Redis port |
| `JWT_SECRET`               | (required)                       | JWT signing secret — **change in production** |
| `ACCESS_TOKEN_MINUTES`     | 15                               | Access token TTL |
| `REFRESH_TOKEN_HOURS`      | 8                                | Refresh token TTL |
| `OPENAI_API_KEY`           | (optional)                       | For NL query agent |
| `GROQ_API_KEY`             | (optional)                       | Alternative to OpenAI |
| `AI_PROVIDER`              | pattern                          | `pattern` \| `openai` \| `groq` |
| `RATE_LIMIT`               | 100                              | Gateway requests/min per IP |
| `REACT_APP_API_URL`        | http://localhost:8000            | Frontend API base URL |

---

## Useful Commands

```bash
# View logs for a specific service
docker compose logs -f auth-service

# Restart a single service
docker compose restart billing-service

# Check health of all services
curl http://localhost:8000/health

# Stop everything
docker compose down

# Stop and remove volumes (wipes database)
docker compose down -v
```

---

## Architecture Notes

- Each service owns its own PostgreSQL database — no cross-service DB joins
- Stock deduction uses `SELECT FOR UPDATE` to prevent race conditions
- `stock_ledger` and `audit_logs` are append-only — never UPDATE or DELETE
- Invoice confirmation triggers stock deduction via HTTP call to inventory service
- Replenishment order receipt auto-creates inventory batch
- AI anomaly detection fires notifications to notification service
- API gateway handles CORS, rate limiting (100 req/min/IP), circuit breaker, and correlation IDs
- All services emit structured JSON logs

# MedAxis Platform

> A production-grade pharmacy operations platform built with Python microservices, PostgreSQL, Redis, and Docker.

[![CI](https://github.com/KUMARankit23/MedAxis_Ai/actions/workflows/ci.yml/badge.svg)](https://github.com/KUMARankit23/MedAxis_Ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)

---

## Features

- **8 independent microservices** — each with its own PostgreSQL database, Alembic migrations, and Swagger docs
- **JWT authentication** with role-based access control (admin, supervisor, pharmacist, inventory_planner)
- **AI-powered demand forecasting** (scikit-learn LinearRegression) and **anomaly detection** (IsolationForest)
- **Conversational NL→SQL** agent (OpenAI GPT-4o-mini with pattern-matching fallback)
- **Redis-backed rate limiting** (sliding window) and **circuit breaker** at the API gateway
- **Prometheus metrics** + structured JSON logging with correlation IDs across all services
- **Production-ready** Docker Compose with nginx reverse proxy, TLS, automated DB backups, and pgAdmin

---

## Architecture

```
Browser / Mobile
      │
      ▼ HTTPS (nginx :443)
┌─────────────────────────────────────────────────────────┐
│              API Gateway  :8000                         │
│   Rate limiting · JWT forwarding · Circuit breaker      │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────┘
   │      │      │      │      │      │      │
 :8001  :8002  :8003  :8004  :8005  :8006  :8007
 Auth   Inv   Bill  Repl   Rep    AI   Notif
   │      │      │      │      │      │      │
  DB    DB    DB    DB    DB    DB    DB
       (PostgreSQL 15 — one database per service)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full design documentation.

---

## Services

| Service | Port | Responsibility |
|---|---|---|
| API Gateway | 8000 | Single entry point, rate limiting, routing, circuit breaker |
| Auth | 8001 | JWT auth, RBAC, user management, audit logs |
| Inventory | 8002 | Products, batches, FEFO stock deduction, ledger |
| Billing | 8003 | Prescriptions, OTC/Rx invoicing, GST calculation |
| Replenishment | 8004 | Reorder lifecycle, AI-triggered PO suggestions |
| Reporting | 8005 | BI dashboards, sales analytics, store performance |
| AI Insights | 8006 | Demand forecasting, anomaly detection, NL queries |
| Notification | 8007 | Event-driven alerts |

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (includes Docker Compose)
- Python 3.12+ (for the seed script only)

### 1. Clone & configure

```bash
git clone https://github.com/KUMARankit23/MedAxis_Ai.git
cd MedAxis_Ai

# Create .env from template and edit the required values
make env
# or: cp .env.example .env
```

Minimum required values in `.env`:
```env
DB_PASSWORD=your-strong-password
JWT_SECRET=your-64-char-random-hex-string
```

Generate a JWT secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Start all services

```bash
make up
# or: docker compose up -d --build
```

First startup takes ~2-3 minutes while images build. Monitor progress:
```bash
make logs
```

### 3. Seed demo data

```bash
make seed
# or: python init-db/02_seed_data.py
```

### 4. Access the platform

| URL | Description |
|---|---|
| http://localhost:3000 | React frontend |
| http://localhost:8000 | API Gateway |
| http://localhost:8001/docs | Auth Service Swagger |
| http://localhost:8002/docs | Inventory Service Swagger |
| http://localhost:8003/docs | Billing Service Swagger |
| http://localhost:8004/docs | Replenishment Service Swagger |
| http://localhost:8005/docs | Reporting Service Swagger |
| http://localhost:8006/docs | AI Insights Service Swagger |

**Default admin credentials:**
```
username: admin
password: Admin@123
```
> Change immediately in production.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI 0.111, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 15 (one DB per service), Alembic migrations |
| Cache | Redis 7 |
| Auth | PyJWT, bcrypt, RBAC |
| AI / ML | scikit-learn (LinearRegression, IsolationForest), OpenAI GPT-4o-mini |
| Frontend | React, Axios, Recharts, React Router |
| Proxy | nginx 1.25 (TLS termination, security headers) |
| Observability | Prometheus metrics, Sentry, structured JSON logging |
| CI/CD | GitHub Actions (lint → test → Docker build → push to GHCR) |

---

## Common Commands

```bash
make up           # Start all services (dev)
make down         # Stop all services
make logs         # Tail all logs
make seed         # Seed demo data
make test         # Run test suite
make lint         # Lint with ruff
make cache-clear  # Clear Redis reporting cache
make health       # Check gateway health endpoint
make help         # Show all available commands
```

---

## Production Deployment

```bash
# 1. Configure production .env (strong secrets, real domain, etc.)
cp .env.example .env

# 2. Generate or install TLS certificates
bash nginx/generate-self-signed-cert.sh   # self-signed (dev/staging)
# For production: place fullchain.pem and privkey.pem in nginx/certs/

# 3. Set REACT_APP_API_URL to your public HTTPS domain in .env
# 4. Start the production stack
make prod-up
```

See [SETUP.md](SETUP.md) for the full production deployment guide including PostgreSQL tuning, Redis auth, and backup configuration.

---

## API Reference

### Auth
```
POST /auth/login            → { access_token, refresh_token, user }
POST /auth/refresh          → { access_token, refresh_token }
POST /auth/users            → UserResponse            [admin only]
GET  /auth/users            → [UserResponse]          [admin only]
GET  /auth/audit-logs       → [AuditLogResponse]      [admin/supervisor]
```

### Inventory
```
POST  /inventory/medicines              → MedicineResponse
GET   /inventory/medicines              → [MedicineResponse]
POST  /inventory/batches                → BatchResponse
POST  /inventory/deduct                 → { deducted, remaining_stock }
GET   /inventory/stock/{outlet_id}      → [StockLevelResponse]
GET   /inventory/alerts/low-stock       → [LowStockItem]
GET   /inventory/alerts/expiring        → [ExpiringBatchItem]
GET   /inventory/ledger/{medicine_id}   → [LedgerResponse]
```

### Billing
```
POST /billing/invoices                  → InvoiceResponse
POST /billing/invoices/{id}/confirm     → InvoiceResponse
POST /billing/invoices/{id}/cancel      → { message }
POST /billing/invoices/{id}/refund      → { message, refunded_amount }
GET  /billing/invoices                  → [InvoiceResponse]
```

### Replenishment
```
GET  /replenishment/orders              → [OrderResponse]
POST /replenishment/orders              → OrderResponse
POST /replenishment/orders/{id}/approve → OrderResponse   [supervisor]
POST /replenishment/orders/{id}/receive → { message }
```

### Reporting
```
GET /reporting/dashboard                → DashboardKPIs
GET /reporting/sales/summary            → SalesSummary
GET /reporting/sales/top-products       → [TopProduct]
GET /reporting/stores/performance       → [StorePerformance]
GET /reporting/inventory/low-stock      → [LowStockItem]
GET /reporting/inventory/expiry         → [ExpiringBatch]
```

### AI Insights
```
POST /ai/forecast                       → ForecastResponse
GET  /ai/forecasts                      → [ForecastResult]
POST /ai/anomalies/detect               → AnomalyResponse
GET  /ai/anomalies                      → [AnomalyLog]
POST /ai/anomalies/{id}/resolve         → { message }
POST /ai/query                          → NLQueryResponse   (NL → SQL)
```

---

## Roles & Permissions

| Role | Access |
|---|---|
| `admin` | Full access to all services |
| `supervisor` | Analytics, stock transfers, anomaly alerts, replenishment approval |
| `pharmacist` | Invoice creation, batch receiving, OTC/Rx sales |
| `inventory_planner` | Products, batches, purchase orders, replenishment suggestions |

---

## Project Structure

```
MedAxis_Ai/
├── services/                  # 8 microservices
│   ├── api-gateway/
│   ├── auth-service/
│   ├── inventory-service/
│   ├── billing-service/
│   ├── replenishment-service/
│   ├── reporting-service/
│   ├── ai-insights-service/
│   └── notification-service/
├── shared/                    # Shared utilities (logging, middleware, observability)
├── frontend/                  # React application
├── init-db/                   # DB creation SQL + seed data script
├── nginx/                     # Reverse proxy config and TLS certs (gitignored)
├── scripts/                   # Backup script and pgAdmin config
├── tests/                     # Integration test suite
├── .github/workflows/         # CI (lint+test) and CD (Docker push to GHCR)
├── docker-compose.yml         # Development stack
├── docker-compose.prod.yml    # Production stack (no exposed ports except nginx)
├── Makefile                   # Common developer commands
├── prometheus.yml             # Prometheus scrape config
└── .env.example               # Environment variable template
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, branching strategy, commit message format, and PR checklist.

## License

[MIT](LICENSE)

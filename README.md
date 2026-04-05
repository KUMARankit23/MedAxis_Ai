# MedAxis Platform — Pharmacy Operations Platform

A microservices platform for managing pharmacy operations across 85 outlets and a central warehouse.
Built with Python (FastAPI), PostgreSQL, Redis, and Docker.

---

## Services

| Service | Port | Responsibility |
|---|---|---|
| API Gateway | 8000 | Single entry point, rate limiting, routing |
| Auth Service | 8001 | JWT authentication, RBAC, user management, audit logs |
| Inventory Service | 8002 | Products, batches, stock levels, FEFO deduction, ledger |
| Billing Service | 8003 | Prescriptions, OTC/Rx invoicing, GST calculation |
| Replenishment Service | 8004 | Reorder lifecycle, AI-triggered PO suggestions |
| Reporting Service | 8005 | BI dashboards, sales analytics, store performance |
| AI Insights Service | 8006 | Demand forecasting, anomaly detection, NL queries |
| Notification Service | 8007 | Event-driven alerts |

---

## Tech Stack

- **Backend** — Python 3.12, FastAPI, SQLAlchemy 2.0 (async)
- **Database** — PostgreSQL 15 (one database per service)
- **Cache / Events** — Redis 7
- **Auth** — JWT (PyJWT), bcrypt
- **AI** — scikit-learn (forecasting + anomaly), OpenAI/Groq (NL queries)
- **Deployment** — Docker, Docker Compose, Kubernetes-ready

---

## Quick Start

```bash
cp .env.example .env
# Edit .env — set DB_PASSWORD and JWT_SECRET at minimum
docker compose up -d --build
```

Seed demo data after services are up:
```bash
python init-db/02_seed_data.py
```

---

## Default Admin

```
username: admin
password: Admin@123
```
> Change this immediately in production.

---

## API Documentation (Swagger UI)

| Service | URL |
|---|---|
| Auth | http://localhost:8001/docs |
| Inventory | http://localhost:8002/docs |
| Billing | http://localhost:8003/docs |
| Replenishment | http://localhost:8004/docs |
| Reporting | http://localhost:8005/docs |
| AI Insights | http://localhost:8006/docs |

---

## Roles

| Role | Access |
|---|---|
| `admin` | Full access |
| `supervisor` | Analytics, stock transfers, anomaly alerts, replenishment approval |
| `pharmacist` | Sales, invoice creation, batch receiving |
| `inventory_planner` | Products, batches, purchase orders, replenishment |

---

## API Contracts

### Auth Service
```
POST /auth/login          → { access_token, refresh_token, user }
POST /auth/refresh        → { access_token, refresh_token, user }
POST /auth/verify         → { sub, role, outlet_id }  [internal]
POST /auth/users          → UserResponse
GET  /auth/users          → [UserResponse]
GET  /auth/audit-logs     → [AuditLogResponse]
```

### Inventory Service
```
POST  /inventory/medicines              → MedicineResponse
GET   /inventory/medicines              → [MedicineResponse]
POST  /inventory/batches                → BatchResponse
POST  /inventory/deduct                 → { deducted, remaining_stock }
POST  /inventory/adjust                 → { before, after }
GET   /inventory/stock/{outlet_id}      → [StockLevelResponse]
GET   /inventory/alerts/low-stock       → [LowStockItem]
GET   /inventory/alerts/expiring        → [ExpiringBatchItem]
GET   /inventory/ledger/{medicine_id}   → [LedgerResponse]
```

### Billing Service
```
POST /billing/prescriptions             → PrescriptionResponse
POST /billing/invoices                  → InvoiceResponse
POST /billing/invoices/{id}/confirm     → InvoiceResponse
POST /billing/invoices/{id}/cancel      → { message }
POST /billing/invoices/{id}/refund      → { message, refunded_amount }
GET  /billing/invoices                  → [InvoiceResponse]
```

### Replenishment Service
```
GET  /replenishment/orders              → [OrderResponse]
POST /replenishment/orders              → OrderResponse
POST /replenishment/orders/{id}/approve → OrderResponse
POST /replenishment/orders/{id}/mark-ordered → { message }
POST /replenishment/orders/{id}/receive → { message }
```

### Reporting Service
```
GET /reporting/dashboard                → DashboardKPIs
GET /reporting/sales/summary            → SalesSummary
GET /reporting/sales/top-products       → [TopProduct]
GET /reporting/stores/performance       → [StorePerformance]
GET /reporting/inventory/low-stock      → [LowStockItem]
GET /reporting/inventory/expiry         → [ExpiringBatch]
```

### AI Insights Service
```
POST /ai/forecast                       → ForecastResponse  (LinearRegression demand forecast)
GET  /ai/forecasts                      → [ForecastResult]
POST /ai/anomalies/detect               → AnomalyResponse   (IsolationForest spike/drop detection)
POST /ai/anomalies/stock-mismatch       → AnomalyResponse
GET  /ai/anomalies                      → [AnomalyLog]
POST /ai/anomalies/{id}/resolve         → { message }
POST /ai/query                          → NLQueryResponse   (NL → SQL via pattern matching / OpenAI)
```

---

## Notes

- Each service owns its own PostgreSQL database — no cross-service DB joins
- Stock deduction uses `SELECT FOR UPDATE` to prevent race conditions
- All AI outputs include `explanation` and `confidence_score` fields
- Replenishment suggestions require supervisor approval before becoming orders
- Conversational AI generates SELECT-only SQL — write operations are blocked
- See `ARCHITECTURE.md` for system design details
- See `SETUP.md` for local development without Docker

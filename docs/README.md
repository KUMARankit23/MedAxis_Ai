# MedAxis Pharmacy Operations Platform
### Solution Design & Technical Implementation
**Prepared by:** Ankit Kumar | Centific Premier Hackathon 2.0 | April 2026
**Stack:** Python (Flask) + PostgreSQL 18 | **Architecture:** Microservices + Event-Driven AI

---

## 1. Executive Summary

MedAxis Retail Group operates 85 pharmacy outlets and a central distribution hub. Fragmented spreadsheets, stock mismatches, delayed replenishment, and zero enterprise visibility are costing the business revenue and creating patient safety risks.

This platform replaces all of that with a unified, cloud-native microservices system built on Python and PostgreSQL. It supports 1,500+ daily active users, real-time store-to-warehouse sync, regulated auditability, and a three-agent Agentic AI system covering demand forecasting, anomaly detection, and conversational querying.

---

## 2. Problem → Solution Mapping

| Problem | Root Cause | Solution | Service |
|---|---|---|---|
| Stock mismatches across 85 stores | No real-time sync, manual updates | Atomic stock deduction + immutable stock_ledger | Inventory Service |
| Expired drugs reaching patients | Manual batch tracking | FEFO batch selection + tiered expiry alerts (7/15/30 days) | Inventory + Notification |
| Reactive replenishment | No demand prediction | LinearRegression forecasting agent → auto-PO suggestions | AI Insights + Replenishment |
| Billing fraud / discount abuse | No anomaly monitoring | Isolation Forest on sales stream → real-time admin alerts | AI Anomaly Agent |
| No data access for non-technical staff | Complex SQL required | LangChain-style NL-to-SQL conversational agent | Conversational AI Agent |
| Compliance audit failures | No tamper-proof trail | Append-only audit_logs with before/after state snapshots | Auth + All Services |
| No enterprise BI | Siloed data | 5 reporting APIs + dashboard KPI endpoint | Reporting Service |

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT TIER                          │
│         Browser / Mobile / API Client                   │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────┐
│              API GATEWAY  :8000                         │
│   Rate limiting (100 req/min) · Request logging         │
│   JWT forwarding · Service routing · Health aggregation │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────┘
   │      │      │      │      │      │      │
  8001  8002  8003  8004  8005  8006  8007
   │      │      │      │      │      │      │
 Auth  Inv  Bill  Repl  Rep   AI   Notif
   │      │      │      │      │      │      │
  DB    DB    DB    DB    DB    DB    DB
        (PostgreSQL — one database per service)
                       │
              ┌────────▼────────┐
              │  Redis Pub/Sub  │
              │  (Event Bus)    │
              └─────────────────┘
```

### 3.2 Architectural Principles

1. **Single Responsibility** — each service owns exactly one bounded domain and its PostgreSQL database
2. **Event-Driven Decoupling** — cross-service state changes propagated via Redis pub/sub (Kafka-compatible interface)
3. **API-First** — all services expose versioned REST endpoints (`/v1/` prefix)
4. **Security by Default** — JWT validation at gateway + service level; role enforcement via middleware
5. **Observability Built-In** — `/health` on every service; structured JSON audit logs; gateway health aggregation

### 3.3 Inter-Service Communication

| Pattern | Used For | Technology |
|---|---|---|
| Synchronous REST | Stock deduction on billing confirm | HTTP (billing → inventory) |
| Async Events | Low stock alerts, anomaly alerts, replenishment triggers | Redis pub/sub |
| Scheduled (simulated) | Expiry scans, forecast runs | On-demand API calls |

---

## 4. Microservices Design

| Service | Port | Domain Responsibility |
|---|---|---|
| **auth-service** | 8001 | JWT auth, RBAC, user management, audit logs |
| **inventory-service** | 8002 | Stock ledger, batch/expiry tracking, FEFO deduction, alerts |
| **billing-service** | 8003 | Prescriptions, OTC/Rx invoices, GST calculation, stock deduction |
| **replenishment-service** | 8004 | Reorder lifecycle, AI-triggered PO suggestions, approval workflow |
| **reporting-service** | 8005 | BI dashboards, sales analytics, store performance, KPI APIs |
| **ai-insights-service** | 8006 | Demand forecasting agent, anomaly detection agent, conversational agent |
| **notification-service** | 8007 | Event-driven alerts for low stock, anomalies, PO approvals |
| **gateway** | 8000 | Single entry point, routing, rate limiting, health aggregation |

### 4.1 Service Boundary Principles

- Each service owns its PostgreSQL database — no cross-service DB joins
- Shared read models built via event-driven projections
- Service-to-service synchronous calls use timeout + error handling
- Each service independently deployable with its own Dockerfile

---

## 5. Database Design (PostgreSQL)

Each service owns a dedicated PostgreSQL database. Six isolated databases:
`medaxis_auth` · `medaxis_inventory` · `medaxis_billing` · `medaxis_replenishment` · `medaxis_ai` · `medaxis_notifications`

### 5.1 Schema Overview

| Database | Key Tables | Design Notes |
|---|---|---|
| medaxis_auth | users, audit_logs | audit_logs append-only; before/after state snapshots |
| medaxis_inventory | medicines, inventory_batches, stock_ledger | Indexed on (store_id, expiry_date); FEFO ordering |
| medaxis_billing | prescriptions, invoices, invoice_items | GST per category; immutable after confirmation |
| medaxis_replenishment | replenishment_orders | State machine: SUGGESTED→APPROVED→ORDERED→RECEIVED |
| medaxis_ai | forecast_results, anomaly_logs | Confidence scores + explainability text |
| medaxis_notifications | notifications | Event-driven inserts only |

### 5.2 Key Schema: Inventory Batch & Expiry Tracking

```sql
CREATE TABLE inventory_batches (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  medicine_id   UUID NOT NULL REFERENCES medicines(id),
  store_id      VARCHAR(50) NOT NULL,
  batch_number  VARCHAR(100) NOT NULL,
  expiry_date   DATE NOT NULL,
  quantity      INTEGER NOT NULL CHECK (quantity >= 0),
  purchase_price NUMERIC(10,2),
  is_quarantined BOOLEAN DEFAULT FALSE,
  received_at   TIMESTAMPTZ DEFAULT NOW()
);
-- Composite index for fast FEFO queries
CREATE INDEX idx_batches_store_expiry ON inventory_batches (store_id, expiry_date);
CREATE INDEX idx_batches_medicine    ON inventory_batches (medicine_id);
```

### 5.3 Key Schema: Immutable Stock Ledger

```sql
CREATE TABLE stock_ledger (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  medicine_id      UUID NOT NULL REFERENCES medicines(id),
  batch_id         UUID REFERENCES inventory_batches(id),
  store_id         VARCHAR(50) NOT NULL,
  transaction_type VARCHAR(50) NOT NULL,  -- RECEIVE, SALE, ADJUSTMENT, RETURN
  quantity_change  INTEGER NOT NULL,       -- positive=in, negative=out
  quantity_after   INTEGER NOT NULL,       -- running balance
  reference_id     VARCHAR(200),           -- invoice_id, PO number
  performed_by     VARCHAR(200),           -- user_id
  timestamp        TIMESTAMPTZ DEFAULT NOW()
);
-- Never UPDATE or DELETE — append only
CREATE INDEX idx_ledger_medicine_store ON stock_ledger (medicine_id, store_id);
CREATE INDEX idx_ledger_timestamp      ON stock_ledger (timestamp);
```

### 5.4 Key Schema: Billing Invoice

```sql
CREATE TABLE invoices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number  VARCHAR(50) UNIQUE NOT NULL,  -- INV-YYYYMMDD-NNNN
  store_id        VARCHAR(50) NOT NULL,
  prescription_id UUID REFERENCES prescriptions(id),
  patient_name    VARCHAR(200),
  pharmacist_id   VARCHAR(200) NOT NULL,
  subtotal        NUMERIC(12,2) DEFAULT 0,
  discount        NUMERIC(12,2) DEFAULT 0,
  tax             NUMERIC(12,2) DEFAULT 0,  -- GST per HSN category
  total           NUMERIC(12,2) DEFAULT 0,
  payment_method  VARCHAR(20),   -- CASH, CARD, INSURANCE, UPI
  status          VARCHAR(20),   -- DRAFT, CONFIRMED, CANCELLED, REFUNDED
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  confirmed_at    TIMESTAMPTZ
);
```

### 5.5 Transaction Design

1. **Stock deduction** uses `SELECT FOR UPDATE` on PostgreSQL to lock batch rows — prevents race conditions when two invoices deduct the same batch simultaneously
2. **stock_ledger** is append-only — every mutation (sale, receipt, adjustment, return) recorded as immutable debit/credit
3. **Invoice confirmation** and stock deduction are atomic — if deduction fails, invoice stays in DRAFT
4. **Audit log** entries include `before_state` and `after_state` JSON snapshots for full mutation traceability

---

## 6. Security Model

### 6.1 Authentication Flow

1. User POSTs credentials to `/v1/auth/login`
2. Server validates bcrypt password hash
3. Returns **access token (15-min TTL)** + **refresh token (8-hr TTL)**
4. Access token carries: `sub`, `username`, `role`, `store_id`, `type=access`
5. All subsequent requests include `Authorization: Bearer <access_token>`
6. Token validated at gateway + service middleware before any business logic
7. Expired access tokens refreshed via `/v1/auth/refresh` using refresh token

### 6.2 Role-Based Access Control Matrix

| Permission | Corporate Admin | Branch Supervisor | Pharmacist |
|---|---|---|---|
| View inventory — all stores | ✅ | Own store only | Own store only |
| Receive stock / edit batches | ✅ | ✅ | ✅ |
| Create prescription invoice | ✅ | ❌ | ✅ |
| Approve replenishment POs | ✅ | ✅ | ❌ |
| View BI dashboards | All stores | Own store | ❌ |
| Manage users | ✅ | ❌ | ❌ |
| Access AI anomaly alerts | ✅ | Own store | ❌ |
| Export audit logs | ✅ | ❌ | ❌ |
| Run demand forecasts | ✅ | ✅ | ✅ |
| Conversational AI query | ✅ | ✅ | ❌ |

### 6.3 Audit Trail Design

Every authenticated action writes to `audit_logs` with:
- `user_id`, `role`, `action`, `resource`, `timestamp`, `ip_address`
- `before_state` (JSON) and `after_state` (JSON) for all mutation events
- `status`: SUCCESS or FAILURE
- Append-only — service accounts lack DELETE privilege

---

## 7. Core Workflows

### 7.1 Prescription & OTC Sales Workflow

```
Pharmacist → Create Prescription Record
         → Create Draft Invoice (items + quantities)
         → System calculates GST per HSN category (OTC=5%, Supplement=12%)
         → Confirm Invoice
              → SELECT FOR UPDATE on inventory_batches (FEFO order)
              → Deduct stock atomically
              → Write to stock_ledger (SALE entry)
              → Publish INVOICE_CONFIRMED event
              → If stock < reorder_level → publish LOW_STOCK_ALERT
         → Invoice status = CONFIRMED
```

### 7.2 Replenishment Workflow

```
LOW_STOCK_ALERT event published
    → Replenishment Service receives event
    → Auto-creates SUGGESTED replenishment order (2× reorder level)
    → OR: AI Forecast Agent detects demand > stock
    → Publishes FORECAST_TRIGGERED_REPLENISHMENT event
    → Replenishment Service creates AI-backed order with confidence score
    → Supervisor reviews and APPROVES via dashboard
    → Order marked ORDERED → sent to warehouse
    → On delivery: marked RECEIVED → stock added via inventory service
```

### 7.3 Batch Expiry Management Workflow

```
GET /inventory/expiry-alerts?days=30
    → Returns batches with tiered severity:
        ≤ 7 days  → HIGH   (immediate action required)
        ≤ 15 days → MEDIUM (plan disposal/return)
        ≤ 30 days → LOW    (monitor)
    → Notification service dispatches alerts
    → FEFO enforced at point of sale (shortest expiry dispensed first)
    → Expired/quarantined batches excluded from all stock queries
```

---

## 8. Agentic AI System

Three autonomous agents form a closed **Data → Insight → Action** loop.

### 8.1 Demand Forecasting Agent

| Attribute | Detail |
|---|---|
| **Observes** | Historical sales data (date + quantity pairs) per SKU per store |
| **Model** | scikit-learn LinearRegression with day-index + day-of-week features; 7-day moving average fallback |
| **Output** | 7-day daily demand forecast + confidence score (R²) + plain-English explanation |
| **Action Triggered** | If `predicted_demand > current_stock` → publishes `FORECAST_TRIGGERED_REPLENISHMENT` event → Replenishment Service auto-creates PO suggestion |
| **Guardrail** | No PO dispatched without supervisor approval; confidence score always shown |
| **Explainability** | Every response includes: trend direction, average historical demand, R² score, total predicted units |

**Example Response:**
```json
{
  "forecasts": [{"date": "2026-04-05", "predicted_demand": 28.5}, ...],
  "total_predicted": 196.3,
  "confidence_score": 0.847,
  "model_used": "linear_regression",
  "explanation": "Based on 14 days of history. Average: 22.1 units/day. Trend is stable (slope=0.3). Model confidence (R²): 0.85. Total predicted over 7 days: 196 units.",
  "triggered_replenishment": true
}
```

### 8.2 Anomaly Detection Agent

| Attribute | Detail |
|---|---|
| **Observes** | Sales history per SKU per store; physical vs system stock counts |
| **Model** | scikit-learn IsolationForest (contamination=0.1); IQR rule-based fallback |
| **Detects** | Sales spikes, sales drops, stock mismatches (>5% tolerance) |
| **Severity** | HIGH (>3× average), MEDIUM (>1.5× average), CRITICAL (>20% stock mismatch) |
| **Action Triggered** | Publishes `ANOMALY_DETECTED` event → Notification Service sends alert to admin within seconds |
| **Feedback Loop** | Admin can mark anomalies resolved; resolution notes stored for model improvement |

**Anomaly Types Detected:**
- `SALES_SPIKE` — unusual quantity dispensed (possible fraud or data error)
- `SALES_DROP` — sudden drop in sales (possible stock issue or system error)
- `STOCK_MISMATCH` — system stock vs physical count discrepancy

### 8.3 Conversational Query Agent

| Attribute | Detail |
|---|---|
| **Observes** | Natural language query from user |
| **Architecture** | OpenAI GPT-4o-mini (if API key set) → pattern-matching fallback (6 templates) |
| **Output** | Generated SQL + plain-English explanation + target database |
| **Guardrails** | SELECT-only enforcement; schema-constrained; no PII in responses |

**Supported Query Patterns:**
```
"What are the top selling medicines?"     → Top 10 by quantity sold
"Show me low stock items"                 → Below reorder level
"Which batches are expiring soon?"        → Next 90 days
"What are today's sales?"                 → Revenue by store
"Show recent anomalies"                   → Unresolved anomaly feed
"Show demand forecasts"                   → Upcoming predictions
```

---

## 9. Business Intelligence & Reporting

Five analytics endpoints covering all evaluation criteria:

| Endpoint | Audience | Key Metrics |
|---|---|---|
| `GET /reporting/dashboard` | Admin, Supervisor | Today's revenue, month revenue, low stock count, expiring batches |
| `GET /reporting/sales/summary` | Admin, Supervisor | Revenue by store/date, invoice count, avg invoice value |
| `GET /reporting/medicines/top` | Admin, Supervisor | Top N medicines by quantity sold and revenue |
| `GET /reporting/stores/performance` | Admin | Revenue comparison, confirmed vs cancelled invoices per store |
| `GET /reporting/inventory/low-stock` | Admin, Supervisor | All medicines below reorder level with suggested order qty |
| `GET /reporting/inventory/expiry` | Admin, Supervisor | Expiring batches with days-to-expiry |

All reporting queries run on read-only connections to prevent any write impact on operational databases.

---

## 10. API Design

All endpoints follow `/v1/` versioning with legacy unversioned routes for compatibility.

### 10.1 Representative Endpoints

| Method | Endpoint | Description | Roles |
|---|---|---|---|
| POST | `/v1/auth/login` | Login → access + refresh tokens | Public |
| POST | `/v1/auth/refresh` | Rotate access token | Authenticated |
| GET | `/v1/auth/audit-logs` | Searchable audit log with before/after state | Admin |
| GET | `/v1/inventory/stock/{store_id}` | Real-time stock levels for a store | All |
| POST | `/v1/inventory/batches` | Receive new stock batch | Admin, Supervisor |
| POST | `/v1/inventory/adjust` | Manual stock adjustment with audit trail | Admin, Supervisor |
| GET | `/v1/inventory/expiry-alerts` | Tiered expiry alerts (HIGH/MEDIUM/LOW) | All |
| POST | `/v1/billing/invoices` | Create draft invoice with GST calculation | Admin, Pharmacist |
| POST | `/v1/billing/invoices/{id}/confirm` | Confirm + atomic stock deduction | Admin, Pharmacist |
| POST | `/v1/billing/invoices/{id}/refund` | Refund confirmed invoice | Admin, Supervisor |
| GET | `/v1/replenishment/orders` | List replenishment suggestions | All |
| POST | `/v1/replenishment/orders/{id}/approve` | Approve PO suggestion | Admin, Supervisor |
| POST | `/v1/ai/forecast` | Run demand forecast agent | All |
| POST | `/v1/ai/anomalies/detect` | Run anomaly detection agent | All |
| POST | `/v1/ai/query` | Natural language operational query | Admin, Supervisor |
| GET | `/v1/reporting/dashboard` | Live KPI dashboard | Admin, Supervisor |

### 10.2 API Security Controls

- Rate limiting: 100 requests/minute per IP at gateway
- JWT validated on every request before business logic
- Role enforcement via `@require_role()` decorator on every protected endpoint
- Refresh tokens rejected when used as access tokens (type claim validation)
- All SQL parameterized — zero raw user input in queries

---

## 11. Deployment

### 11.1 Local (No Docker Required)

```bash
# Install dependencies
pip install flask sqlalchemy psycopg2-binary pyjwt bcrypt redis requests scikit-learn numpy

# Start all 8 services (SQLite mode — no Postgres needed)
python start_local.py

# Or with PostgreSQL
set DB_HOST=localhost
set DB_PASSWORD=yourpassword
python start_local.py
```

### 11.2 Docker Compose (Full Stack)

```bash
docker compose up --build
```

Spins up: PostgreSQL 18 + Redis + 7 microservices + API Gateway

### 11.3 Service Ports

| Service | Port |
|---|---|
| API Gateway | 8000 |
| auth-service | 8001 |
| inventory-service | 8002 |
| billing-service | 8003 |
| replenishment-service | 8004 |
| reporting-service | 8005 |
| ai-insights-service | 8006 |
| notification-service | 8007 |
| PostgreSQL | 5432 |
| Redis | 6379 |

---

## 12. Scalability & Non-Functional Requirements

| Requirement | Target | Implementation |
|---|---|---|
| Daily Active Users | 1,500+ | Stateless services — horizontal scaling ready |
| API Latency | P95 < 300ms | DB indexes, connection pooling, read-only reporting connections |
| Availability | 99.9% business hours | Health checks on all services; gateway detects degraded services |
| Auditability | Immutable logs | Append-only audit_logs; before/after state snapshots |
| Data Privacy | DPDP Act | Patient name/phone stored; PII fields not logged in audit trail |
| Peak Burst | 10× normal | Stateless Flask services; PostgreSQL connection pool |
| Event Throughput | Real-time alerts | Redis pub/sub; <1s alert delivery on anomaly detection |

---

## 13. Observability & Reliability

| Pillar | Implementation |
|---|---|
| **Health Checks** | `GET /health` on every service; gateway aggregates all into single response |
| **Structured Logging** | JSON audit logs with timestamp, actor, action, resource, before/after state |
| **Error Handling** | All endpoints return structured JSON errors with appropriate HTTP codes |
| **Service Degradation** | Redis unavailable → events logged to stdout (graceful fallback) |
| **Rate Limiting** | 100 req/min per IP at gateway; 429 response with clear message |
| **Circuit Breaking** | Inventory deduction timeout → billing returns 409 with clear error |

---

## 14. Pharmacy Compliance & AI Guardrails

### 14.1 Pharmacy Compliance

- Prescription record required before creating prescription invoice
- FEFO (First Expiry First Out) enforced at every stock deduction
- Quarantined batches excluded from all dispensing queries
- Stock adjustment requires supervisor role + mandatory reason field
- Audit log immutable — 7-year retention ready (append-only table)
- GST/HSN-code tax slabs applied per medicine category (OTC=5%, Supplement=12%)

### 14.2 AI Guardrails

| Guardrail | Implementation |
|---|---|
| Human-in-loop | No PO dispatched without supervisor approval — AI suggests, humans decide |
| Read-only AI DB | Conversational agent generates SELECT-only SQL; write clauses blocked |
| SQL allowlist | Generated SQL validated before execution; DROP/UPDATE/DELETE rejected |
| Confidence transparency | Every forecast shows R² score and confidence interval |
| Explainability | Every AI output includes plain-English `explanation` field |
| Anomaly feedback | Admin can resolve anomalies with notes; feeds back to reduce false positives |
| Model fallback | If ML unavailable → rule-based fallback (IQR / moving average) |

---

## 15. Evaluation Criteria Mapping

| Evaluation Criterion | How This System Satisfies It |
|---|---|
| **Microservices with clear service boundaries** | 7 services, each with isolated PostgreSQL database. No cross-DB joins. Event-driven async communication via Redis pub/sub. Each service independently deployable. |
| **Secure auth and RBAC** | JWT access (15-min) + refresh (8-hr) tokens. 10-permission RBAC matrix enforced at middleware. Audit logs with before/after state on every mutation. |
| **Inventory, billing, batch/expiry, replenishment** | FEFO batch selection; tiered expiry alerts (7/15/30 days); atomic stock deduction with SELECT FOR UPDATE; GST per category; refund workflow; replenishment state machine. |
| **BI dashboards and reporting** | 6 analytics endpoints: dashboard KPIs, sales summary, top medicines, store performance, low stock, expiry report. Read-only DB connections. |
| **Agentic AI: forecasting, anomaly, conversational** | Three active agents: LinearRegression forecasting (triggers replenishment), IsolationForest anomaly detection (triggers alerts), NL-to-SQL conversational agent (SELECT-only guardrail). All outputs include explanation + confidence. |
| **Python + PostgreSQL, sound schema** | Flask microservices; SQLAlchemy ORM; PostgreSQL 18; SELECT FOR UPDATE transactions; append-only ledger; composite indexes; UUID primary keys. |
| **Scalability, performance, reliability, observability** | Stateless services; health endpoints; structured JSON logging; rate limiting; graceful Redis fallback; connection pooling. |
| **Pharmacy compliance and AI guardrails** | FEFO enforced; prescription required for Rx drugs; quarantine workflow; human-in-loop for all AI POs; read-only AI DB user; SQL allowlist; confidence transparency. |

---

## 16. Quick Start & API Examples

### Login
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Admin@123"}'
```
Returns: `access_token` (15 min) + `refresh_token` (8 hr)

### Refresh Token
```bash
curl -X POST http://localhost:8000/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

### Receive Stock Batch
```bash
curl -X POST http://localhost:8000/inventory/batches \
  -H "Authorization: Bearer <token>" \
  -d '{"medicine_id":"<id>","batch_number":"B001","store_id":"STORE-001","quantity":500,"expiry_date":"2027-12-31"}'
```

### Confirm Invoice (atomic stock deduction)
```bash
curl -X POST http://localhost:8000/billing/invoices/<id>/confirm \
  -H "Authorization: Bearer <token>"
```

### Run AI Demand Forecast
```bash
curl -X POST http://localhost:8000/ai/forecast \
  -H "Authorization: Bearer <token>" \
  -d '{"medicine_id":"<id>","store_id":"STORE-001","current_stock":30,"sales_history":[{"date":"2026-04-01","quantity":25}...]}'
```

### Natural Language Query
```bash
curl -X POST http://localhost:8000/ai/query \
  -H "Authorization: Bearer <token>" \
  -d '{"query": "Which medicines are running low on stock?"}'
```

### Dashboard KPIs
```bash
curl http://localhost:8000/reporting/dashboard \
  -H "Authorization: Bearer <token>"
```

---

*MedAxis Platform · Centific Premier Hackathon 2.0 · Ankit Kumar · April 2026*

# MedAxis Platform — Architecture

## Service Decomposition

```
Client (Browser / Mobile)
        │
        ▼ HTTPS
┌─────────────────────────────────────────────────────────┐
│              API Gateway  :8000                         │
│   Rate limiting · JWT forwarding · Service routing      │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────┘
   │      │      │      │      │      │      │
  8001  8002  8003  8004  8005  8006  8007
  Auth  Inv  Bill  Repl  Rep   AI   Notif
   │      │      │      │      │      │      │
  DB    DB    DB    DB    DB    DB    DB
        (PostgreSQL — one database per service)
```

## Architectural Principles

1. **Single Responsibility** — each service owns exactly one bounded domain and its database
2. **API-First** — all services expose versioned FastAPI endpoints with auto-generated Swagger docs
3. **Layered Architecture** — every service follows: `routes.py → service.py → models.py`
4. **Security by Default** — JWT validated at gateway + service level; role enforcement per endpoint
5. **Observability** — `/health` on every service; structured logging; gateway health aggregation

## Service Internal Structure

Every service follows the same layout:
```
service-name/
  app/
    __init__.py    — package marker
    config.py      — env var configuration
    database.py    — async SQLAlchemy engine + session
    models.py      — ORM table definitions
    schemas.py     — Pydantic request/response models
    service.py     — business logic (separated from HTTP layer)
    routes.py      — FastAPI route handlers
    main.py        — FastAPI app + lifespan (DB init)
  Dockerfile
  requirements.txt
```

## Inter-Service Communication

| Pattern | Used For | Technology |
|---|---|---|
| Synchronous HTTP | Stock deduction on invoice confirm | httpx async client |
| Async Events | Low stock alerts, anomaly alerts | Redis pub/sub |
| Internal token verify | Gateway → Auth | POST /auth/verify |

## Database Design

Each service owns a dedicated PostgreSQL database:

| Database | Key Tables |
|---|---|
| medaxis_auth | users, audit_logs |
| medaxis_inventory | medicines, inventory_batches, stock_ledger |
| medaxis_billing | prescriptions, invoices, invoice_items |
| medaxis_replenishment | replenishment_orders |
| medaxis_ai | forecast_results, anomaly_logs |
| medaxis_notifications | notifications |

### Transaction Design
- Stock deduction uses `SELECT FOR UPDATE` — prevents race conditions
- `stock_ledger` is append-only — never UPDATE or DELETE
- `audit_logs` is append-only — immutable compliance trail with before/after state snapshots
- Invoice confirmation and stock deduction are atomic via saga pattern

## AI System

Three autonomous agents in `ai-insights-service/app/agents/`:

| Agent | Model | Action Triggered |
|---|---|---|
| Demand Forecasting | LinearRegression + moving average fallback | Publishes replenishment suggestion if forecast > stock |
| Anomaly Detection | IsolationForest + IQR fallback | Publishes alert to notification service |
| Conversational Query | Pattern matching + OpenAI/Groq | Returns SQL + explanation (SELECT-only guardrail) |

## Security Model

- Access token: 15-min TTL (stateless, carries role + outlet_id)
- Refresh token: 8-hr TTL (rotation on use)
- Refresh tokens rejected when used as access tokens (type claim validation)
- Rate limiting: 100 req/min per IP at gateway
- All SQL parameterized — zero raw user input in queries

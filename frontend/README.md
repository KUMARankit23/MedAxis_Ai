# MedAxis Frontend

React-based UI for the MedAxis Pharmacy Operations Platform.

## Pages

| Page | Route | Roles |
|---|---|---|
| Login | /login | Public |
| Dashboard | / | Admin, Supervisor |
| Inventory | /inventory | All |
| Billing | /billing | All |
| Replenishment | /replenishment | Admin, Supervisor |
| AI Insights | /ai | Admin, Supervisor |
| Reports | /reports | Admin, Supervisor |
| Audit Logs | /audit | Admin only |

## Setup

```bash
cd frontend
npm install
npm start
```

Runs on http://localhost:3000
Backend must be running on http://localhost:8000

## Features

- JWT auth with auto token refresh
- Role-based navigation (menu items hidden by role)
- Live dashboard KPIs with charts
- Inventory management + batch receiving
- Invoice creation with GST calculation
- AI demand forecast with chart visualization
- Anomaly detection with severity badges
- Natural language query interface
- Store performance reports with charts
- Audit log viewer with before/after state

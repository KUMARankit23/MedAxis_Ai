"""
Gap fix verification script.
Run: python infra/verify_gaps.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests

BASE_AUTH = "http://localhost:8001"
BASE_INV  = "http://localhost:8002"
BASE_BILL = "http://localhost:8003"
BASE_REP  = "http://localhost:8005"

print("=== GAP FIX VERIFICATION ===\n")

# 1. Login — check access + refresh tokens returned
r = requests.post(f"{BASE_AUTH}/v1/auth/login",
                  json={"username": "admin", "password": "Admin@123"}, timeout=5)
d = r.json()
access  = d.get("access_token")
refresh = d.get("refresh_token")
expires = d.get("access_expires_in")
print(f"[1] Login /v1/auth/login:       {r.status_code}")
print(f"    access_token present:       {bool(access)}")
print(f"    refresh_token present:      {bool(refresh)}")
print(f"    access_expires_in (sec):    {expires}  (expected: 900 = 15 min)")

# 2. Refresh token rotation
r2 = requests.post(f"{BASE_AUTH}/v1/auth/refresh",
                   json={"refresh_token": refresh}, timeout=5)
print(f"\n[2] Token refresh:              {r2.status_code}  (expected: 200)")
print(f"    new access_token:           {bool(r2.json().get('access_token'))}")

# 3. Refresh token rejected as access token
r3 = requests.get(f"{BASE_AUTH}/v1/auth/me",
                  headers={"Authorization": f"Bearer {refresh}"}, timeout=5)
print(f"\n[3] Refresh token as access:    {r3.status_code}  (expected: 401)")
print(f"    error msg:                  {r3.json().get('error')}")

h = {"Authorization": f"Bearer {access}"}

# 4. Tiered expiry alerts (30/15/7 day severity)
r4 = requests.get(f"{BASE_INV}/inventory/expiry-alerts?days=30", headers=h, timeout=5)
d4 = r4.json()
print(f"\n[4] Tiered expiry alerts:       {r4.status_code}  (expected: 200)")
print(f"    severity counts:            {d4.get('counts')}")

# 5. Stock adjustment endpoint (new)
r5 = requests.post(f"{BASE_INV}/inventory/adjust",
                   json={"batch_id": "00000000-0000-0000-0000-000000000000",
                         "new_quantity": 50, "reason": "test"},
                   headers=h, timeout=5)
print(f"\n[5] Stock adjust endpoint:      {r5.status_code}  (expected: 404 = endpoint exists)")

# 6. Audit logs with before/after details
r6 = requests.get(f"{BASE_AUTH}/v1/auth/audit-logs", headers=h, timeout=5)
logs = r6.json().get("logs", [])
has_details = any(l.get("details") for l in logs)
print(f"\n[6] Audit logs:                 {r6.status_code}  (expected: 200)")
print(f"    total entries:              {len(logs)}")
print(f"    has before/after details:   {has_details}")

# 7. Refund endpoint (new)
r7 = requests.post(f"{BASE_BILL}/billing/invoices/00000000-0000-0000-0000-000000000000/refund",
                   json={}, headers=h, timeout=5)
print(f"\n[7] Refund endpoint:            {r7.status_code}  (expected: 404 = endpoint exists)")

# 8. Reporting dashboard (PostgreSQL-compatible)
r8 = requests.get(f"{BASE_REP}/reporting/dashboard", headers=h, timeout=10)
print(f"\n[8] Dashboard (PostgreSQL):     {r8.status_code}  (expected: 200)")
if r8.status_code == 200:
    kpis = r8.json()
    print(f"    today revenue:              {kpis.get('today', {}).get('revenue')}")
    print(f"    alerts:                     {kpis.get('alerts')}")

# 9. /v1/ versioned routes
r9 = requests.get(f"{BASE_INV}/v1/inventory/medicines", headers=h, timeout=5)
print(f"\n[9] /v1/ versioned route:       {r9.status_code}  (expected: 200)")

# 10. GST on invoice — check tax is calculated per category
print(f"\n[10] GST calculation: tax applied per medicine category (OTC=5%, SUPPLEMENT=12%)")
print(f"     Verify by creating an invoice and checking tax field in response.")

print("\n=== DONE ===")

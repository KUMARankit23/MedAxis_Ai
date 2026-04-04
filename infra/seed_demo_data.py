"""
Demo data seeder — run AFTER the platform is started.
Usage:
    python start_local.py        (terminal 1)
    python infra/seed_demo_data.py  (terminal 2)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
import time
from datetime import date, timedelta

# Hit services directly — no gateway needed for seeding
AUTH  = "http://localhost:8001"
INV   = "http://localhost:8002"
BILL  = "http://localhost:8003"
AI    = "http://localhost:8006"


def wait_for_services(retries=15, delay=2):
    print("Waiting for services", end="", flush=True)
    for _ in range(retries):
        try:
            r = requests.get(f"{AUTH}/health", timeout=2)
            if r.status_code == 200:
                print(" ready.")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(delay)
    print("\nAuth service not reachable. Is the platform running?")
    return False


def post(base, path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(f"{base}{path}", json=data, headers=headers, timeout=30)
        print(f"POST {path} → {r.status_code}: {r.text[:120]}")
        return r.json()
    except Exception as e:
        print(f"POST {path} → ERROR: {e}")
        return {}


def get(base, path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"{base}{path}", headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        print(f"GET {path} → ERROR: {e}")
        return {}


if not wait_for_services():
    sys.exit(1)

# 1. Login as admin
print("\n=== Login ===")
resp = post(AUTH, "/auth/login", {"username": "admin", "password": "Admin@123"})
token = resp.get("token")
if not token:
    print("Login failed.")
    sys.exit(1)
print(f"Logged in as admin. Token: {token[:40]}...")

# 2. Create users
print("\n=== Create Users ===")
post(AUTH, "/auth/register", {"username": "pharmacist1", "email": "ph1@medaxis.com",
     "password": "Pharma@123", "role": "pharmacist", "store_id": "STORE-001"}, token)
post(AUTH, "/auth/register", {"username": "supervisor1", "email": "sup1@medaxis.com",
     "password": "Super@123", "role": "supervisor", "store_id": "STORE-001"}, token)

# 3. Create medicines
print("\n=== Create Medicines ===")
m1 = post(INV, "/inventory/medicines", {
    "name": "Paracetamol 500mg", "category": "OTC",
    "unit_price": 2.50, "reorder_level": 50, "reorder_quantity": 200,
    "manufacturer": "PharmaCo"
}, token)
m2 = post(INV, "/inventory/medicines", {
    "name": "Amoxicillin 250mg", "category": "PRESCRIPTION",
    "unit_price": 8.00, "reorder_level": 30, "reorder_quantity": 100,
    "manufacturer": "MediLabs"
}, token)
m3 = post(INV, "/inventory/medicines", {
    "name": "Ibuprofen 400mg", "category": "OTC",
    "unit_price": 3.50, "reorder_level": 40, "reorder_quantity": 150,
}, token)

med_ids = [
    m1.get("medicine", {}).get("id"),
    m2.get("medicine", {}).get("id"),
    m3.get("medicine", {}).get("id"),
]
print(f"Medicine IDs: {med_ids}")

# 4. Receive stock batches
print("\n=== Receive Stock ===")
for mid in med_ids:
    if mid:
        post(INV, "/inventory/batches", {
            "medicine_id": mid,
            "batch_number": f"BATCH-2024-{mid[:6]}",
            "store_id": "STORE-001",
            "quantity": 200,
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
        }, token)

# 5. Create and confirm an invoice
print("\n=== Create Invoice ===")
if med_ids[0]:
    inv = post(BILL, "/billing/invoices", {
        "store_id": "STORE-001",
        "patient_name": "Jane Smith",
        "items": [
            {"medicine_id": med_ids[0], "medicine_name": "Paracetamol 500mg",
             "quantity": 10, "unit_price": 2.50},
        ]
    }, token)
    inv_id = inv.get("invoice", {}).get("id")
    if inv_id:
        post(BILL, f"/billing/invoices/{inv_id}/confirm", {}, token)

# 6. Run AI forecast
print("\n=== AI Forecast ===")
if med_ids[0]:
    post(AI, "/ai/forecast", {
        "medicine_id": med_ids[0],
        "medicine_name": "Paracetamol 500mg",
        "store_id": "STORE-001",
        "current_stock": 190,
        "sales_history": [
            {"date": (date.today() - timedelta(days=i)).isoformat(), "quantity": 20 + i % 5}
            for i in range(14, 0, -1)
        ]
    }, token)

# 7. Run anomaly detection
print("\n=== Anomaly Detection ===")
if med_ids[0]:
    post(AI, "/ai/anomalies/detect", {
        "medicine_id": med_ids[0],
        "medicine_name": "Paracetamol 500mg",
        "store_id": "STORE-001",
        "sales_history": [
            {"date": (date.today() - timedelta(days=i)).isoformat(), "quantity": 20 if i != 3 else 200}
            for i in range(10, 0, -1)
        ]
    }, token)

print("\n=== Seed complete ===")
print(f"  Gateway:   http://localhost:8000")
print(f"  Dashboard: http://localhost:8005/reporting/dashboard  (needs token)")
print(f"  Token:     {token}")

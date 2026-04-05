"""
Seed demo data — run after all services are started.

Usage:
    python init-db/02_seed_data.py

Requires: pip install requests
"""
import sys, time, requests
from datetime import date, timedelta

AUTH = "http://localhost:8001"
INV  = "http://localhost:8002"
BILL = "http://localhost:8003"
AI   = "http://localhost:8006"


def wait(url, retries=15, delay=2):
    print("Waiting for services", end="", flush=True)
    for _ in range(retries):
        try:
            if requests.get(f"{url}/health", timeout=2).status_code == 200:
                print(" ready."); return True
        except: pass
        print(".", end="", flush=True); time.sleep(delay)
    print("\nServices not reachable."); return False


def post(base, path, data, token=None):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(f"{base}{path}", json=data, headers=h, timeout=30)
        print(f"  POST {path} → {r.status_code}")
        return r.json()
    except Exception as e:
        print(f"  POST {path} → ERROR: {e}"); return {}


if not wait(AUTH): sys.exit(1)

# Login
resp = post(AUTH, "/auth/login", {"username": "admin", "password": "Admin@123"})
token = resp.get("access_token")
if not token: print("Login failed"); sys.exit(1)
print(f"\nLogged in. Token: {token[:40]}...\n")

# Users
print("=== Users ===")
post(AUTH, "/auth/users", {"username":"pharmacist1","email":"ph1@medaxis.com","password":"Pharma@123","role":"pharmacist","outlet_id":"OUTLET-001"}, token)
post(AUTH, "/auth/users", {"username":"supervisor1","email":"sup1@medaxis.com","password":"Super@123","role":"supervisor","outlet_id":"OUTLET-001"}, token)
post(AUTH, "/auth/users", {"username":"planner1","email":"plan1@medaxis.com","password":"Plan@123","role":"inventory_planner"}, token)

# Medicines
print("\n=== Medicines ===")
meds = [
    {"name":"Paracetamol 500mg","category":"OTC","unit_price":2.50,"reorder_level":50,"reorder_quantity":200,"manufacturer":"PharmaCo"},
    {"name":"Amoxicillin 250mg","category":"PRESCRIPTION","unit_price":8.00,"reorder_level":30,"reorder_quantity":100,"manufacturer":"MediLabs"},
    {"name":"Ibuprofen 400mg","category":"OTC","unit_price":3.50,"reorder_level":40,"reorder_quantity":150,"manufacturer":"GenPharma"},
    {"name":"Metformin 500mg","category":"PRESCRIPTION","unit_price":5.00,"reorder_level":25,"reorder_quantity":120,"manufacturer":"DiabCare"},
    {"name":"Vitamin D3 1000IU","category":"OTC","unit_price":4.00,"reorder_level":60,"reorder_quantity":250,"manufacturer":"NutriLabs"},
]
med_ids = []
for m in meds:
    r = post(INV, "/inventory/medicines", m, token)
    if r.get("id"): med_ids.append(r["id"])

# Stock batches
print("\n=== Stock Batches ===")
for mid in med_ids:
    post(INV, "/inventory/batches", {
        "medicine_id": mid, "batch_number": f"BATCH-{mid[:6].upper()}",
        "outlet_id": "OUTLET-001", "quantity": 300,
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
    }, token)

# Invoice
print("\n=== Invoice ===")
if med_ids:
    inv = post(BILL, "/billing/invoices", {
        "outlet_id": "OUTLET-001", "patient_name": "Rahul Sharma",
        "items": [{"medicine_id": med_ids[0], "medicine_name": "Paracetamol 500mg",
                   "quantity": 10, "unit_price": 2.50, "category": "OTC"}]
    }, token)
    if inv.get("id"):
        post(BILL, f"/billing/invoices/{inv['id']}/confirm", {}, token)

# AI Forecast
print("\n=== AI Forecast ===")
if med_ids:
    post(AI, "/ai/forecast", {
        "medicine_id": med_ids[0], "medicine_name": "Paracetamol 500mg",
        "outlet_id": "OUTLET-001", "current_stock": 290,
        "sales_history": [{"date": (date.today()-timedelta(days=i)).isoformat(), "quantity": 20+i%5}
                           for i in range(14, 0, -1)]
    }, token)

# Anomaly detection
print("\n=== Anomaly Detection ===")
if med_ids:
    post(AI, "/ai/anomalies/detect", {
        "medicine_id": med_ids[0], "medicine_name": "Paracetamol 500mg",
        "outlet_id": "OUTLET-001",
        "sales_history": [{"date": (date.today()-timedelta(days=i)).isoformat(),
                           "quantity": 20 if i != 3 else 200} for i in range(10, 0, -1)]
    }, token)

print("\n=== Seed complete ===")
print("  Gateway:  http://localhost:8000")
print("  Swagger:  http://localhost:8001/docs  (auth)")
print("           http://localhost:8002/docs  (inventory)")
print("           http://localhost:8003/docs  (billing)")
print("           http://localhost:8005/docs  (reporting)")
print("           http://localhost:8006/docs  (AI insights)")

"""
Seed demo data — run after all services are started.

Usage:
    python init-db/02_seed_data.py

Requires: pip install requests
"""
import sys
import time
import requests
from datetime import date, timedelta

AUTH  = "http://localhost:8001"
INV   = "http://localhost:8002"
BILL  = "http://localhost:8003"
REPL  = "http://localhost:8004"
AI    = "http://localhost:8006"
NOTIF = "http://localhost:8007"


def wait(url, retries=20, delay=3):
    print(f"Waiting for {url}", end="", flush=True)
    for _ in range(retries):
        try:
            if requests.get(f"{url}/health", timeout=2).status_code == 200:
                print(" ready.")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(delay)
    print(f"\n{url} not reachable after {retries * delay}s")
    return False


def post(base, path, data, token=None, label=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(f"{base}{path}", json=data, headers=h, timeout=30)
        status = "OK" if r.status_code in (200, 201) else "FAIL"
        print(f"  [{status}] POST {path} -> {r.status_code}" + (f" ({label})" if label else ""))
        return r.json() if r.content else {}
    except Exception as e:
        print(f"  [ERR] POST {path} -> ERROR: {e}")
        return {}


def get(base, path, token=None):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"{base}{path}", headers=h, timeout=10)
        return r.json() if r.content else {}
    except Exception:
        return {}


# ── Wait for services ─────────────────────────────────────────────────────────
for svc_url in [AUTH, INV, BILL]:
    if not wait(svc_url):
        sys.exit(1)

# ── Login ─────────────────────────────────────────────────────────────────────
print("\n=== Auth ===")
resp = post(AUTH, "/auth/login", {"username": "admin", "password": "Admin@123"})
token = resp.get("access_token")
if not token:
    print("Login failed:", resp)
    sys.exit(1)
print(f"  Logged in as admin. Token: {token[:40]}...")

# ── Users ─────────────────────────────────────────────────────────────────────
print("\n=== Users ===")
post(AUTH, "/auth/users", {
    "username": "pharmacist1", "email": "ph1@medaxis.com",
    "password": "Pharma@123", "role": "pharmacist", "outlet_id": "OUTLET-001",
}, token, "pharmacist")
post(AUTH, "/auth/users", {
    "username": "supervisor1", "email": "sup1@medaxis.com",
    "password": "Super@123", "role": "supervisor", "outlet_id": "OUTLET-001",
}, token, "supervisor")
post(AUTH, "/auth/users", {
    "username": "planner1", "email": "plan1@medaxis.com",
    "password": "Plan@123", "role": "inventory_planner",
}, token, "inventory_planner")

# ── Medicines ─────────────────────────────────────────────────────────────────
print("\n=== Medicines ===")
MEDICINES = [
    {"name": "Paracetamol 500mg",   "category": "OTC",          "unit_price": 2.50,  "reorder_level": 50,  "reorder_quantity": 200, "manufacturer": "PharmaCo",   "unit": "tablets"},
    {"name": "Amoxicillin 250mg",   "category": "PRESCRIPTION", "unit_price": 8.00,  "reorder_level": 30,  "reorder_quantity": 100, "manufacturer": "MediLabs",   "unit": "capsules"},
    {"name": "Ibuprofen 400mg",     "category": "OTC",          "unit_price": 3.50,  "reorder_level": 40,  "reorder_quantity": 150, "manufacturer": "GenPharma",  "unit": "tablets"},
    {"name": "Metformin 500mg",     "category": "PRESCRIPTION", "unit_price": 5.00,  "reorder_level": 25,  "reorder_quantity": 120, "manufacturer": "DiabCare",   "unit": "tablets"},
    {"name": "Vitamin D3 1000IU",   "category": "OTC",          "unit_price": 4.00,  "reorder_level": 60,  "reorder_quantity": 250, "manufacturer": "NutriLabs",  "unit": "softgels"},
    {"name": "Atorvastatin 10mg",   "category": "PRESCRIPTION", "unit_price": 12.00, "reorder_level": 20,  "reorder_quantity": 80,  "manufacturer": "CardioMed",  "unit": "tablets"},
    {"name": "Omeprazole 20mg",     "category": "OTC",          "unit_price": 6.50,  "reorder_level": 35,  "reorder_quantity": 140, "manufacturer": "GastroLabs", "unit": "capsules"},
    {"name": "Cetirizine 10mg",     "category": "OTC",          "unit_price": 1.80,  "reorder_level": 45,  "reorder_quantity": 180, "manufacturer": "AllerCare",  "unit": "tablets"},
    {"name": "Azithromycin 500mg",  "category": "PRESCRIPTION", "unit_price": 18.00, "reorder_level": 15,  "reorder_quantity": 60,  "manufacturer": "MediLabs",   "unit": "tablets"},
    {"name": "Insulin Glargine",    "category": "CONTROLLED",   "unit_price": 450.00,"reorder_level": 10,  "reorder_quantity": 30,  "manufacturer": "DiabCare",   "unit": "vials"},
]

med_ids = []
for m in MEDICINES:
    r = post(INV, "/inventory/medicines", m, token, m["name"])
    if r.get("id"):
        med_ids.append({"id": r["id"], "name": r["name"], "category": r["category"]})

# ── Stock Batches (multiple outlets) ─────────────────────────────────────────
print("\n=== Stock Batches ===")
OUTLETS = ["OUTLET-001", "OUTLET-002", "OUTLET-003", "WAREHOUSE"]
for med in med_ids:
    for outlet in OUTLETS:
        qty = 500 if outlet == "WAREHOUSE" else 150
        post(INV, "/inventory/batches", {
            "medicine_id": med["id"],
            "batch_number": f"BATCH-{med['id'][:6].upper()}-{outlet}",
            "outlet_id": outlet,
            "quantity": qty,
            "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
            "purchase_price": 1.5,
        }, token, f"{med['name']} @ {outlet}")

# Add a near-expiry batch for expiry alert testing
if med_ids:
    post(INV, "/inventory/batches", {
        "medicine_id": med_ids[0]["id"],
        "batch_number": "BATCH-EXPIRING-SOON",
        "outlet_id": "OUTLET-001",
        "quantity": 20,
        "expiry_date": (date.today() + timedelta(days=10)).isoformat(),
    }, token, "near-expiry batch")

# ── Invoices ──────────────────────────────────────────────────────────────────
print("\n=== Invoices ===")
if len(med_ids) >= 3:
    inv = post(BILL, "/billing/invoices", {
        "outlet_id": "OUTLET-001",
        "patient_name": "Rahul Sharma",
        "payment_method": "CASH",
        "items": [
            {"medicine_id": med_ids[0]["id"], "medicine_name": med_ids[0]["name"],
             "quantity": 10, "unit_price": 2.50, "category": "OTC"},
            {"medicine_id": med_ids[2]["id"], "medicine_name": med_ids[2]["name"],
             "quantity": 5, "unit_price": 3.50, "category": "OTC"},
        ],
    }, token, "draft invoice")

    if inv.get("id"):
        post(BILL, f"/billing/invoices/{inv['id']}/confirm", {}, token, "confirm invoice")

    # Second invoice (draft only)
    post(BILL, "/billing/invoices", {
        "outlet_id": "OUTLET-002",
        "patient_name": "Priya Patel",
        "payment_method": "UPI",
        "items": [
            {"medicine_id": med_ids[1]["id"], "medicine_name": med_ids[1]["name"],
             "quantity": 2, "unit_price": 8.00, "category": "PRESCRIPTION",
             "is_prescription_item": True},
        ],
    }, token, "draft invoice 2")

# ── Replenishment Orders ──────────────────────────────────────────────────────
print("\n=== Replenishment Orders ===")
if med_ids:
    order = post(REPL, "/replenishment/orders", {
        "medicine_id": med_ids[0]["id"],
        "medicine_name": med_ids[0]["name"],
        "outlet_id": "OUTLET-001",
        "suggested_quantity": 200,
        "current_stock": 45,
        "notes": "Auto-suggested: stock below reorder level",
    }, token, "suggested order")

# ── AI Forecast ───────────────────────────────────────────────────────────────
print("\n=== AI Forecast ===")
if med_ids:
    post(AI, "/ai/forecast", {
        "medicine_id": med_ids[0]["id"],
        "medicine_name": med_ids[0]["name"],
        "outlet_id": "OUTLET-001",
        "current_stock": 140,
        "sales_history": [
            {"date": (date.today() - timedelta(days=i)).isoformat(), "quantity": 18 + (i % 5)}
            for i in range(14, 0, -1)
        ],
    }, token, "demand forecast")

# ── Anomaly Detection ─────────────────────────────────────────────────────────
print("\n=== Anomaly Detection ===")
if med_ids:
    post(AI, "/ai/anomalies/detect", {
        "medicine_id": med_ids[0]["id"],
        "medicine_name": med_ids[0]["name"],
        "outlet_id": "OUTLET-001",
        "sales_history": [
            {"date": (date.today() - timedelta(days=i)).isoformat(),
             "quantity": 20 if i != 3 else 250}
            for i in range(10, 0, -1)
        ],
    }, token, "anomaly detection")

# ── Notification ──────────────────────────────────────────────────────────────
print("\n=== Notifications ===")
post(NOTIF, "/notifications", {
    "notification_type": "SYSTEM",
    "message": "MedAxis platform seeded successfully. All services operational.",
    "subject": "Seed Complete",
    "source_service": "seed_script",
}, label="system notification")

print("\n" + "=" * 60)
print("  Seed complete!")
print("=" * 60)
print(f"  Gateway:    http://localhost:8000")
print(f"  Auth:       http://localhost:8001/docs")
print(f"  Inventory:  http://localhost:8002/docs")
print(f"  Billing:    http://localhost:8003/docs")
print(f"  Replenish:  http://localhost:8004/docs")
print(f"  Reporting:  http://localhost:8005/docs")
print(f"  AI:         http://localhost:8006/docs")
print(f"  Notify:     http://localhost:8007/docs")
print()
print("  Default credentials:")
print("    admin        / Admin@123")
print("    pharmacist1  / Pharma@123")
print("    supervisor1  / Super@123")
print("    planner1     / Plan@123")

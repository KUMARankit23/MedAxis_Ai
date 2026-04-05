"""
Start all MedAxis services with PostgreSQL.
Usage: python start_postgres.py

Edit DB_PASSWORD below if your PostgreSQL password changes.
"""
import subprocess, sys, os, time, signal

BASE = os.path.dirname(os.path.abspath(__file__))

# ── PostgreSQL config — update if password changes ───────────────────────────
DB_CONFIG = {
    "DB_HOST":     "localhost",
    "DB_PORT":     "5432",
    "DB_USER":     "postgres",
    "DB_PASSWORD": "258025",
    "JWT_SECRET":  "medaxis-local-secret",
    "ACCESS_TOKEN_MINUTES": "15",
    "PYTHONPATH":  BASE,
}

SERVICES = [
    {"name": "auth-service",          "path": "services/auth-service",          "port": 8001},
    {"name": "inventory-service",     "path": "services/inventory-service",     "port": 8002},
    {"name": "billing-service",       "path": "services/billing-service",       "port": 8003,
     "extra": {"INVENTORY_SERVICE_URL": "http://localhost:8002"}},
    {"name": "replenishment-service", "path": "services/replenishment-service", "port": 8004},
    {"name": "reporting-service",     "path": "services/reporting-service",     "port": 8005},
    {"name": "ai-insights-service",   "path": "services/ai-insights-service",   "port": 8006},
    {"name": "notification-service",  "path": "services/notification-service",  "port": 8007},
    {"name": "gateway",               "path": "gateway",                        "port": 8000},
]

processes = []

def start_service(svc):
    svc_dir = os.path.join(BASE, svc["path"])
    env = os.environ.copy()
    env.update(DB_CONFIG)
    env.update(svc.get("extra", {}))

    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    log = open(os.path.join(BASE, "data", f"{svc['name']}.log"), "w")

    proc = subprocess.Popen([sys.executable, "app.py"], cwd=svc_dir, env=env, stdout=log, stderr=log)
    print(f"  started {svc['name']:30s} → http://localhost:{svc['port']}  (pid {proc.pid})")
    return proc

if __name__ == "__main__":
    print("Starting MedAxis Platform (PostgreSQL mode)\n")
    for svc in SERVICES:
        processes.append(start_service(svc))
        time.sleep(1.5)

    print(f"\nAll services running.")
    print(f"  Gateway:   http://localhost:8000")
    print(f"  Frontend:  http://localhost:3000  (run: cd frontend && npm start)")
    print(f"\nPress Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(5)
            for i, (svc, proc) in enumerate(zip(SERVICES, processes)):
                if proc.poll() is not None:
                    print(f"  [WARN] {svc['name']} exited. Check data/{svc['name']}.log")
    except KeyboardInterrupt:
        print("\nStopping all services...")
        for p in processes:
            try: p.terminate()
            except: pass

"""
Local development launcher — no Docker required.
Starts all 7 microservices + gateway as background processes.

Usage:
    python start_local.py          # start all services
    python start_local.py --stop   # kill all (Windows: taskkill by port)

Requirements: pip install flask sqlalchemy bcrypt pyjwt redis requests scikit-learn
Database: SQLite (auto-created in ./data/ folder, no Postgres needed)
"""
import subprocess
import sys
import os
import time
import signal

BASE = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {"name": "auth-service",          "path": "services/auth-service",          "port": 8001},
    {"name": "inventory-service",     "path": "services/inventory-service",     "port": 8002},
    {"name": "billing-service",       "path": "services/billing-service",       "port": 8003},
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
    # Point Python path to project root so `shared` imports work
    env["PYTHONPATH"] = BASE
    # Use SQLite — no Postgres needed
    env["USE_SQLITE"] = "true"
    env.setdefault("JWT_SECRET", "medaxis-local-dev-secret")

    log_path = os.path.join(BASE, "data", f"{svc['name']}.log")
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    log_file = open(log_path, "w")

    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=svc_dir,
        env=env,
        stdout=log_file,
        stderr=log_file,
    )
    print(f"  started {svc['name']:30s} → http://localhost:{svc['port']}  (pid {proc.pid})")
    return proc


def stop_all():
    """Kill all started processes."""
    for proc in processes:
        try:
            proc.terminate()
        except Exception:
            pass
    print("All services stopped.")


if __name__ == "__main__":
    if "--stop" in sys.argv:
        # On Windows, kill by port using netstat + taskkill
        for svc in SERVICES:
            os.system(f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{svc["port"]}\') do taskkill /F /PID %a 2>nul')
        print("Sent kill signals to all service ports.")
        sys.exit(0)

    print("Starting MedAxis Platform (SQLite mode — no Docker needed)\n")

    for svc in SERVICES:
        proc = start_service(svc)
        processes.append(proc)
        time.sleep(1.5)  # stagger startup so DB init doesn't race

    print(f"\nAll services running.")
    print(f"  Gateway:    http://localhost:8000")
    print(f"  Health:     http://localhost:8000/health")
    print(f"  Logs:       ./data/<service-name>.log")
    print(f"\nPress Ctrl+C to stop all services.\n")

    try:
        # Keep alive — wait for all processes
        while True:
            time.sleep(5)
            # Check if any service died unexpectedly
            for i, (svc, proc) in enumerate(zip(SERVICES, processes)):
                if proc.poll() is not None:
                    print(f"  [WARN] {svc['name']} exited (code {proc.returncode}). Check data/{svc['name']}.log")
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_all()

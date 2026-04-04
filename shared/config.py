"""
Shared configuration loaded from environment variables.
Each service imports this to get consistent settings.

DB mode:
  - Set USE_SQLITE=true (or leave DB_HOST unset) to use local SQLite files.
    This requires zero external dependencies and works on any machine.
  - Set DB_HOST to a real Postgres host for production / Docker deployments.
"""
import os

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "medaxis-super-secret-key-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "8"))

# Database
DB_HOST = os.getenv("DB_HOST", "")          # empty → SQLite mode
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "medaxis")
DB_PASSWORD = os.getenv("DB_PASSWORD", "medaxis123")

# SQLite files are stored in a local `data/` folder next to the project root
_SQLITE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def get_db_url(db_name: str) -> str:
    """
    Return a SQLAlchemy database URL.
    Uses SQLite when DB_HOST is not set (local dev / no Docker).
    Uses PostgreSQL when DB_HOST is configured (Docker / production).
    """
    use_sqlite = os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes") or not DB_HOST
    if use_sqlite:
        os.makedirs(_SQLITE_DIR, exist_ok=True)
        db_path = os.path.join(_SQLITE_DIR, f"{db_name}.db")
        return f"sqlite:///{db_path}"
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{db_name}"

# Redis (for event queue simulation — optional, falls back to logging if unavailable)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Service ports
SERVICE_PORTS = {
    "auth": 8001,
    "inventory": 8002,
    "billing": 8003,
    "replenishment": 8004,
    "reporting": 8005,
    "ai-insights": 8006,
    "notification": 8007,
    "gateway": 8000,
}

# Low stock threshold (units)
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "20"))

# OpenAI (optional — falls back to pattern matching if not set)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

"""
Shared database engine factory.
Handles SQLite (local dev) vs PostgreSQL (Docker/prod) transparently.
"""
from sqlalchemy import create_engine
from shared.config import get_db_url


def make_engine(db_name: str):
    """
    Create a SQLAlchemy engine with the right settings for the backend.
    SQLite needs check_same_thread=False for Flask's multi-threaded requests.
    """
    url = get_db_url(db_name)
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)

"""Replenishment Service — Database session management."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy.orm import sessionmaker
from shared.db_utils import make_engine
from models import Base

engine = make_engine("medaxis_replenishment")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)

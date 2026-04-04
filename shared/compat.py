"""
Cross-database compatibility helpers.
SQLite doesn't support PostgreSQL-specific types like UUID.
This module provides drop-in replacements that work on both.
"""
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator
import uuid


class GUID(TypeDecorator):
    """
    Platform-independent UUID type.
    - PostgreSQL: stores as native UUID
    - SQLite: stores as 36-char string
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(str(value))

    @staticmethod
    def new():
        """Generate a new UUID (use as column default)."""
        return uuid.uuid4

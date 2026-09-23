"""Shared column types and helpers used by all module models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID


class GUID(TypeDecorator):
    """
    Backward-compatible UUID type kept for Phase 1 models.
    Uses native PostgreSQL UUID when connected to PostgreSQL,
    falls back to String(36) for SQLite (test compatibility).
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# JSONB on PostgreSQL, plain JSON elsewhere (SQLite local development).
JSONType = JSON().with_variant(JSONB(), "postgresql")

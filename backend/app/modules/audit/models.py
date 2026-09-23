"""Database models for the audit module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Text, ForeignKey, DateTime, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.projects.models import Project



class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    project: Mapped["Project | None"] = relationship("Project", back_populates="audit_logs", foreign_keys="[AuditLog.project_id]")

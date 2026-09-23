"""Database models for the rates module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Numeric, ForeignKey, DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.projects.models import Project



class Rate(Base):
    __tablename__ = "rates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    item_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    rate_per_unit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    rate_source: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    project: Mapped["Project | None"] = relationship("Project", back_populates="rates")

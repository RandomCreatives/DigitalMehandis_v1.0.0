"""Database models for the boq module."""
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



class BOQOutput(Base):
    __tablename__ = "boq_outputs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    total_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="ETB")
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    excel_path: Mapped[str | None] = mapped_column(String(500))

    project: Mapped["Project"] = relationship("Project", back_populates="boq_outputs")

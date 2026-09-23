"""Database models for the bbs module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Numeric, Text, ForeignKey, DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.projects.models import Project



class BBSBar(Base):
    __tablename__ = "bbs_bars"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    bar_mark: Mapped[str | None] = mapped_column(String(50))
    member_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bar_diameter_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    bar_shape: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    clear_length_m: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    hook_length_mm: Mapped[int] = mapped_column(Integer, default=0)
    bend_deduction_mm: Mapped[int] = mapped_column(Integer, default=0)
    cover_top_mm: Mapped[int] = mapped_column(Integer, default=50)
    cover_bottom_mm: Mapped[int] = mapped_column(Integer, default=50)
    lap_length_mm: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    project: Mapped["Project"] = relationship("Project", back_populates="bbs_bars")

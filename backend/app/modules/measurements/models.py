"""Database models for the measurements module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Text, ForeignKey, DateTime, JSON, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.drawings.models import DrawingPage
    from app.modules.projects.models import Project
    from app.modules.elements.models import ProjectElement
    from app.modules.boq_items.models import QuantitySource



class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawing_pages.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    calibration_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawing_calibrations.id", ondelete="SET NULL"), nullable=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    element_category: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[float] = mapped_column(Float, nullable=False)
    final_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    scale_factor_used: Mapped[float | None] = mapped_column(Float)
    points_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#eb6905")
    stroke_width: Mapped[int] = mapped_column(Integer, default=2)
    project_element_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("project_elements.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    page: Mapped["DrawingPage | None"] = relationship("DrawingPage", back_populates="measurements")
    project_element: Mapped["ProjectElement | None"] = relationship("ProjectElement", back_populates="measurements")
    quantity_sources: Mapped[list["QuantitySource"]] = relationship("QuantitySource", back_populates="measurement", cascade="all, delete-orphan")
    project: Mapped["Project"] = relationship("Project", back_populates="measurements", foreign_keys="[Measurement.project_id]")

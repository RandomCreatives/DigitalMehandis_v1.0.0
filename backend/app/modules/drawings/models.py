"""Database models for the drawings module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Numeric, Text, ForeignKey, DateTime, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.calibration.models import DrawingCalibration
    from app.modules.measurements.models import Measurement
    from app.modules.projects.models import Project



class Drawing(Base):
    __tablename__ = "drawings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_mb: Mapped[float | None] = mapped_column(Numeric(10, 2))
    category: Mapped[str | None] = mapped_column(String(50))
    page_count: Mapped[int | None] = mapped_column(Integer)
    scale: Mapped[str | None] = mapped_column(String(50))
    title_block_text: Mapped[str | None] = mapped_column(Text)
    user_notes: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    project: Mapped["Project"] = relationship("Project", back_populates="drawings")


class DrawingPage(Base):
    __tablename__ = "drawing_pages"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[float | None] = mapped_column(Float)
    height_px: Mapped[float | None] = mapped_column(Float)
    width_mm: Mapped[float | None] = mapped_column(Float)
    height_mm: Mapped[float | None] = mapped_column(Float)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    rendered_image_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    calibrations: Mapped[list["DrawingCalibration"]] = relationship(
        "DrawingCalibration", back_populates="page", cascade="all, delete-orphan"
    )
    measurements: Mapped[list["Measurement"]] = relationship(
        "Measurement", back_populates="page", cascade="all, delete-orphan"
    )

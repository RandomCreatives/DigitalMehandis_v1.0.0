"""Database models for the calibration module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Integer, ForeignKey, DateTime, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.drawings.models import DrawingPage
    from app.modules.projects.models import Project



class DrawingCalibration(Base):
    __tablename__ = "drawing_calibrations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawing_pages.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    reference_name: Mapped[str | None] = mapped_column(String(100))
    point_a_x: Mapped[float] = mapped_column(Float, nullable=False)
    point_a_y: Mapped[float] = mapped_column(Float, nullable=False)
    point_b_x: Mapped[float] = mapped_column(Float, nullable=False)
    point_b_y: Mapped[float] = mapped_column(Float, nullable=False)
    pixel_distance: Mapped[float] = mapped_column(Float, nullable=False)
    real_distance: Mapped[float] = mapped_column(Float, nullable=False)
    real_unit: Mapped[str] = mapped_column(String(10), default="m")
    scale_factor: Mapped[float] = mapped_column(Float, nullable=False)
    pixels_per_meter: Mapped[float] = mapped_column(Float, nullable=False)
    floor_level: Mapped[str | None] = mapped_column(String(50))
    grid_reference: Mapped[str | None] = mapped_column(String(100))
    rotation_degrees: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    page: Mapped["DrawingPage | None"] = relationship("DrawingPage", back_populates="calibrations")
    project: Mapped["Project"] = relationship("Project", back_populates="calibrations", foreign_keys="[DrawingCalibration.project_id]")

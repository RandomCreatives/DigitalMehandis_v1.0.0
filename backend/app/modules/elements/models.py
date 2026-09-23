"""Database models for the elements module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, ForeignKey, DateTime, JSON, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.measurements.models import Measurement
    from app.modules.projects.models import Project
    from app.modules.boq_items.models import QuantitySource



class ProjectElement(Base):
    __tablename__ = "project_elements"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    element_code: Mapped[str] = mapped_column(String(50), nullable=False)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    floor_level: Mapped[str | None] = mapped_column(String(50))
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(50), default="MANUAL_ENTRY")
    approx_x: Mapped[float | None] = mapped_column(Float)
    approx_y: Mapped[float | None] = mapped_column(Float)
    geometry_json: Mapped[dict | None] = mapped_column(JSON)
    material: Mapped[str | None] = mapped_column(String(255))
    specification: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    measurements: Mapped[list["Measurement"]] = relationship("Measurement", back_populates="project_element")
    quantity_sources: Mapped[list["QuantitySource"]] = relationship("QuantitySource", back_populates="project_element")
    project: Mapped["Project"] = relationship("Project", back_populates="project_elements", foreign_keys="[ProjectElement.project_id]")

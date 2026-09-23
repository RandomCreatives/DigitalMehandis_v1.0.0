"""Database models for the projects module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Text, ForeignKey, DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.audit.models import AuditLog
    from app.modules.bbs.models import BBSBar
    from app.modules.boq_items.models import BOQItem
    from app.modules.boq.models import BOQOutput
    from app.modules.drawings.models import Drawing
    from app.modules.calibration.models import DrawingCalibration
    from app.modules.measurements.models import Measurement
    from app.modules.elements.models import ProjectElement
    from app.modules.rates.models import Rate
    from app.modules.takeoff.models import TakeoffItem
    from app.modules.auth.models import User



class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    code_of_practice: Mapped[str | None] = mapped_column(String(50))
    unit_system: Mapped[str] = mapped_column(String(10), default="METRIC")
    currency: Mapped[str] = mapped_column(String(3), default="ETB")
    rate_database_version: Mapped[str | None] = mapped_column(String(50))
    scale: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user: Mapped["User"] = relationship("User", back_populates="projects")
    drawings: Mapped[list["Drawing"]] = relationship("Drawing", back_populates="project", cascade="all, delete-orphan")
    takeoff_items: Mapped[list["TakeoffItem"]] = relationship("TakeoffItem", back_populates="project", cascade="all, delete-orphan")
    rates: Mapped[list["Rate"]] = relationship("Rate", back_populates="project", cascade="all, delete-orphan")
    bbs_bars: Mapped[list["BBSBar"]] = relationship("BBSBar", back_populates="project", cascade="all, delete-orphan")
    boq_outputs: Mapped[list["BOQOutput"]] = relationship("BOQOutput", back_populates="project", cascade="all, delete-orphan")

    # ── Phase 2 relationships ─────────────────────────────────────────────────
    # (models defined in other modules; resolved via app.db.registry)
    calibrations: Mapped[list["DrawingCalibration"]] = relationship(
        "DrawingCalibration", back_populates="project", cascade="all, delete-orphan",
        foreign_keys="DrawingCalibration.project_id",
    )
    measurements: Mapped[list["Measurement"]] = relationship(
        "Measurement", back_populates="project", cascade="all, delete-orphan",
        foreign_keys="Measurement.project_id",
    )
    project_elements: Mapped[list["ProjectElement"]] = relationship(
        "ProjectElement", back_populates="project", cascade="all, delete-orphan",
        foreign_keys="ProjectElement.project_id",
    )
    boq_items: Mapped[list["BOQItem"]] = relationship(
        "BOQItem", back_populates="project", cascade="all, delete-orphan",
        foreign_keys="BOQItem.project_id",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="project",
        foreign_keys="AuditLog.project_id",
    )

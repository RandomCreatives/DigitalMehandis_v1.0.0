"""
Phase 2 — Drawing-Aware QS + Federation Foundation
Class order matters for SQLAlchemy forward references:
  DrawingPage → DrawingCalibration → Measurement → ProjectElement
  → BOQItem → BOQItemSource → QuantitySource → AuditLog
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, DateTime, JSON, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def now_utc():
    return datetime.now(timezone.utc)


# ── Drawing Pages ─────────────────────────────────────────────────────────────

class DrawingPage(Base):
    __tablename__ = "drawing_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
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


# ── Drawing Calibration ───────────────────────────────────────────────────────

class DrawingCalibration(Base):
    __tablename__ = "drawing_calibrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("drawing_pages.id", ondelete="SET NULL"), nullable=True)
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
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    page: Mapped["DrawingPage | None"] = relationship("DrawingPage", back_populates="calibrations")
    project: Mapped["Project"] = relationship("Project", back_populates="calibrations", foreign_keys="[DrawingCalibration.project_id]")


# ── Project Elements ──────────────────────────────────────────────────────────

class ProjectElement(Base):
    __tablename__ = "project_elements"
    __table_args__ = (
        # One row per element per revision; ext_uid is the stable handle.
        Index("uq_project_element_uid_revision", "project_id", "ext_uid", "revision", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    element_code: Mapped[str] = mapped_column(String(50), nullable=False)
    # Stable identity across drawing revisions. This is what makes revision
    # diffs, variations (added / omitted / re-measured) and element-level
    # progress possible. Assigned on first sight and never reused.
    ext_uid: Mapped[str | None] = mapped_column(String(64), index=True)
    # Drawing revision this row was measured from (e.g. "Rev A", "R2").
    revision: Mapped[str | None] = mapped_column(String(40))
    # Which strength convention ``material``/``specification`` grade is quoted
    # in: EBCS_2 (cube) or ES_EN_1992_1_1 (cylinder). Null = unstated.
    grade_standard: Mapped[str | None] = mapped_column(String(40))
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)
    discipline: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    floor_level: Mapped[str | None] = mapped_column(String(50))
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(50), default="MANUAL_ENTRY")
    approx_x: Mapped[float | None] = mapped_column(Float)
    approx_y: Mapped[float | None] = mapped_column(Float)
    geometry_json: Mapped[dict | None] = mapped_column(JSON)
    material: Mapped[str | None] = mapped_column(String(255))
    specification: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    measurements: Mapped[list["Measurement"]] = relationship("Measurement", back_populates="project_element")
    quantity_sources: Mapped[list["QuantitySource"]] = relationship("QuantitySource", back_populates="project_element")
    project: Mapped["Project"] = relationship("Project", back_populates="project_elements", foreign_keys="[ProjectElement.project_id]")


# ── Measurements ──────────────────────────────────────────────────────────────

class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("drawing_pages.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    calibration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("drawing_calibrations.id", ondelete="SET NULL"), nullable=True)
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
        UUID(as_uuid=True), ForeignKey("project_elements.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    page: Mapped["DrawingPage | None"] = relationship("DrawingPage", back_populates="measurements")
    project_element: Mapped["ProjectElement | None"] = relationship("ProjectElement", back_populates="measurements")
    quantity_sources: Mapped[list["QuantitySource"]] = relationship("QuantitySource", back_populates="measurement", cascade="all, delete-orphan")
    project: Mapped["Project"] = relationship("Project", back_populates="measurements", foreign_keys="[Measurement.project_id]")


# ── BOQ Items ─────────────────────────────────────────────────────────────────

class BOQItem(Base):
    __tablename__ = "boq_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    item_no: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    trade: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    waste_factor: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    sources: Mapped[list["BOQItemSource"]] = relationship("BOQItemSource", back_populates="boq_item", cascade="all, delete-orphan")
    quantity_sources: Mapped[list["QuantitySource"]] = relationship("QuantitySource", back_populates="boq_item")
    project: Mapped["Project"] = relationship("Project", back_populates="boq_items", foreign_keys="[BOQItem.project_id]")


class BOQItemSource(Base):
    __tablename__ = "boq_item_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    boq_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("boq_items.id", ondelete="CASCADE"), nullable=False)
    suggested_quantity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suggested_quantities.id", ondelete="SET NULL"), nullable=True)
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("measurements.id", ondelete="SET NULL"), nullable=True)
    project_element_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_elements.id", ondelete="SET NULL"), nullable=True)
    contribution_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    boq_item: Mapped["BOQItem"] = relationship("BOQItem", back_populates="sources")


# ── Quantity Sources (defined AFTER BOQItem so forward ref resolves) ──────────

class QuantitySource(Base):
    __tablename__ = "quantity_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    suggested_quantity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suggested_quantities.id", ondelete="CASCADE"), nullable=True
    )
    boq_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boq_items.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("measurements.id", ondelete="SET NULL"), nullable=True)
    project_element_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_elements.id", ondelete="SET NULL"), nullable=True)
    dxf_layer: Mapped[str | None] = mapped_column(String(255))
    dxf_block_name: Mapped[str | None] = mapped_column(String(255))
    dxf_entity_id: Mapped[str | None] = mapped_column(String(255))
    contribution_value: Mapped[float | None] = mapped_column(Float)
    contribution_unit: Mapped[str | None] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    measurement: Mapped["Measurement | None"] = relationship("Measurement", back_populates="quantity_sources")
    project_element: Mapped["ProjectElement | None"] = relationship("ProjectElement", back_populates="quantity_sources")
    boq_item: Mapped["BOQItem | None"] = relationship("BOQItem", back_populates="quantity_sources", foreign_keys="[QuantitySource.boq_item_id]")


# ── Audit Logs ────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    project: Mapped["Project | None"] = relationship("Project", back_populates="audit_logs", foreign_keys="[AuditLog.project_id]")

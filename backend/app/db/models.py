import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Boolean, Integer, Numeric, Text, ForeignKey,
    DateTime, CheckConstraint
)
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class GUID(TypeDecorator):
    """
    Backward-compatible UUID type kept for Phase 1 models.
    Uses native PostgreSQL UUID when connected to PostgreSQL,
    falls back to String(36) for SQLite (test compatibility).
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="STUDENT")
    preferred_language: Mapped[str] = mapped_column(String(5), default="EN")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")


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
    # (models defined in models_phase2.py, imported via Base metadata)
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


class TakeoffItem(Base):
    __tablename__ = "takeoff_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(15, 3), nullable=False)
    section: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    project: Mapped["Project"] = relationship("Project", back_populates="takeoff_items")


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
    # Audit trail for the lap calculation: which code produced lap_length_mm,
    # and which concrete grade was used to derive it. Nullable for legacy rows.
    design_code: Mapped[str | None] = mapped_column(String(40))
    concrete_grade: Mapped[str | None] = mapped_column(String(20))
    section: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    project: Mapped["Project"] = relationship("Project", back_populates="bbs_bars")


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


# ── Suggested Quantities (pending user approval) ──────────────────────────────

class SuggestedQuantity(Base):
    """
    Auto-extracted quantity suggestion from a drawing (DXF or PDF).
    Stays in 'pending' state until the QS professional approves/rejects/edits it.
    Only approved quantities flow into the BOQ.
    """
    __tablename__ = "suggested_quantities"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True)

    discipline: Mapped[str] = mapped_column(String(50), nullable=False)
    element_category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_value: Mapped[float] = mapped_column(Numeric(15, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    source_layer: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=0.8)
    notes: Mapped[str | None] = mapped_column(Text)

    # Approval workflow
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    # PENDING | APPROVED | REJECTED | EDITED

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Federated Quantities (approved, used in BOQ) ──────────────────────────────

class FederatedQuantity(Base):
    """
    Approved quantity — promoted from SuggestedQuantity after user review.
    These are the source of truth for BOQ generation.
    """
    __tablename__ = "federated_quantities"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True)
    suggested_quantity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("suggested_quantities.id", ondelete="SET NULL"), nullable=True)

    discipline: Mapped[str] = mapped_column(String(50), nullable=False)
    element_category: Mapped[str] = mapped_column(String(100), nullable=False)
    element_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_value: Mapped[float] = mapped_column(Numeric(15, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    source_layer: Mapped[str | None] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

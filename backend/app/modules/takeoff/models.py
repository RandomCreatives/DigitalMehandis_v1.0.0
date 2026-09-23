"""Database models for the takeoff module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Numeric, Text, ForeignKey, DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.projects.models import Project



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

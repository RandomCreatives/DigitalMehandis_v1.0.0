"""Database models for the boq_items module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Integer, Text, ForeignKey, DateTime, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.measurements.models import Measurement
    from app.modules.projects.models import Project
    from app.modules.elements.models import ProjectElement



class BOQItem(Base):
    __tablename__ = "boq_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
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
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    sources: Mapped[list["BOQItemSource"]] = relationship("BOQItemSource", back_populates="boq_item", cascade="all, delete-orphan")
    quantity_sources: Mapped[list["QuantitySource"]] = relationship("QuantitySource", back_populates="boq_item")
    project: Mapped["Project"] = relationship("Project", back_populates="boq_items", foreign_keys="[BOQItem.project_id]")


class BOQItemSource(Base):
    __tablename__ = "boq_item_sources"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    boq_item_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("boq_items.id", ondelete="CASCADE"), nullable=False)
    suggested_quantity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("suggested_quantities.id", ondelete="SET NULL"), nullable=True)
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("measurements.id", ondelete="SET NULL"), nullable=True)
    project_element_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("project_elements.id", ondelete="SET NULL"), nullable=True)
    contribution_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    boq_item: Mapped["BOQItem"] = relationship("BOQItem", back_populates="sources")


class QuantitySource(Base):
    __tablename__ = "quantity_sources"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    suggested_quantity_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("suggested_quantities.id", ondelete="CASCADE"), nullable=True
    )
    boq_item_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("boq_items.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer)
    measurement_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("measurements.id", ondelete="SET NULL"), nullable=True)
    project_element_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("project_elements.id", ondelete="SET NULL"), nullable=True)
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

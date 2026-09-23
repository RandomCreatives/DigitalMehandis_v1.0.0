"""Database models for the cost_library module."""
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
    from app.modules.rate_matching.models import ElementRateMatch



class RateSource(Base):
    __tablename__ = "rate_sources"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quarter: Mapped[str | None] = mapped_column(String(50), nullable=True)
    calendar_system: Mapped[str] = mapped_column(String(50), default="EC")
    cost_type: Mapped[str] = mapped_column(String(50), default="DIRECT_COST")
    currency: Mapped[str] = mapped_column(String(10), default="ETB")
    source_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    rate_items: Mapped[list["RateItem"]] = relationship(
        "RateItem", back_populates="rate_source", cascade="all, delete-orphan"
    )
    raw_import_rows: Mapped[list["RawRateImportRow"]] = relationship(
        "RawRateImportRow", back_populates="rate_source", cascade="all, delete-orphan"
    )


class RateItem(Base):
    __tablename__ = "rate_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("rate_items.id", ondelete="CASCADE"), nullable=True
    )
    rate_source_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rate_sources.id", ondelete="CASCADE"), nullable=False
    )
    item_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    work_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sub_category: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    normalized_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direct_cost: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="ETB")
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fiscal_year: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    rate_source: Mapped["RateSource"] = relationship("RateSource", back_populates="rate_items")
    parent: Mapped["RateItem | None"] = relationship("RateItem", remote_side=[id], back_populates="children")
    children: Mapped[list["RateItem"]] = relationship("RateItem", back_populates="parent", cascade="all, delete-orphan")
    element_matches: Mapped[list["ElementRateMatch"]] = relationship(
        "ElementRateMatch", back_populates="rate_item"
    )


class RawRateImportRow(Base):
    __tablename__ = "raw_rate_import_rows"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    rate_source_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rate_sources.id", ondelete="CASCADE"), nullable=False
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_item_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_cost: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parsed_item_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parsed_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    parsed_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    rate_source: Mapped["RateSource"] = relationship("RateSource", back_populates="raw_import_rows")

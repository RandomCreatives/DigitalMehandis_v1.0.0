"""Database models for the rate_matching module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Text, ForeignKey, DateTime, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import TYPE_CHECKING
from app.db.types import GUID, now_utc

if TYPE_CHECKING:
    from app.modules.cost_library.models import RateItem, RateSource



class ProjectPricingSettings(Base):
    __tablename__ = "project_pricing_settings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    selected_rate_source_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("rate_sources.id", ondelete="SET NULL"), nullable=True
    )
    contractor_grade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    overhead_percent: Mapped[float] = mapped_column(Float, default=8.0)
    profit_percent: Mapped[float] = mapped_column(Float, default=10.0)
    tax_percent: Mapped[float] = mapped_column(Float, default=0.0)
    pricing_mode: Mapped[str] = mapped_column(String(50), default="ADDITIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    selected_rate_source: Mapped["RateSource | None"] = relationship("RateSource")


class ElementRateMatch(Base):
    __tablename__ = "element_rate_matches"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    project_element_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project_elements.id", ondelete="CASCADE"), nullable=False
    )
    rate_item_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("rate_items.id", ondelete="SET NULL"), nullable=True
    )
    match_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="SUGGESTED")
    applied_direct_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    applied_final_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    rate_item: Mapped["RateItem | None"] = relationship("RateItem", back_populates="element_matches")

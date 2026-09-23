"""Database models for the cad module."""
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Integer, Text, ForeignKey, DateTime, Float,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.types import GUID, JSONType, now_utc


class DXFLayer(Base):
    __tablename__ = "dxf_layers"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    layer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, default=0)
    classified_as: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    user_override: Mapped[str | None] = mapped_column(String(100))
    strategy_used: Mapped[str | None] = mapped_column(String(50))
    is_ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    user_override: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DXFBlock(Base):
    __tablename__ = "dxf_blocks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    block_name: Mapped[str] = mapped_column(String(255), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)
    classified_as: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    user_override: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DXFEntity(Base):
    __tablename__ = "dxf_entities"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    layer_name: Mapped[str | None] = mapped_column(String(255))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    geometry_json: Mapped[dict | None] = mapped_column(JSONType)
    length: Mapped[float | None] = mapped_column(Float)
    area: Mapped[float | None] = mapped_column(Float)
    text_content: Mapped[str | None] = mapped_column(Text)
    block_name: Mapped[str | None] = mapped_column(String(255))
    position_x: Mapped[float | None] = mapped_column(Float)
    position_y: Mapped[float | None] = mapped_column(Float)
    handle: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class LayerMapping(Base):
    __tablename__ = "layer_mappings_v2" # Renamed to avoid confusion with any potential existing v1

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"))
    layer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline: Mapped[str] = mapped_column(String(10), nullable=False)
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    mapped_by: Mapped[str] = mapped_column(String(20), nullable=False) # system, user
    confidence: Mapped[float | None] = mapped_column(Float)
    is_community: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class BlockMapping(Base):
    __tablename__ = "block_mappings_v2"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"))
    block_name: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline: Mapped[str] = mapped_column(String(10), nullable=False)
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    mapped_by: Mapped[str] = mapped_column(String(20), nullable=False) # system, user
    confidence: Mapped[float | None] = mapped_column(Float)
    is_community: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class LayerMappingTemplate(Base):
    __tablename__ = "layer_mapping_templates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    mappings_json: Mapped[dict] = mapped_column(JSONType, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DrawingRevision(Base):
    __tablename__ = "drawing_revisions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    diff_summary_json: Mapped[dict | None] = mapped_column(JSONType)


class DXFAnalysisJob(Base):
    __tablename__ = "dxf_analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    entities_found: Mapped[int] = mapped_column(Integer, default=0)
    layers_found: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_generated: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class QuantitySuggestion(Base):
    __tablename__ = "quantity_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    drawing_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False)
    discipline: Mapped[str] = mapped_column(String(10), nullable=False)
    task_key: Mapped[str] = mapped_column(String(100), nullable=False)
    task_label: Mapped[str | None] = mapped_column(String(255))

    source_layer: Mapped[str | None] = mapped_column(String(255))
    source_block: Mapped[str | None] = mapped_column(String(255))
    entity_count: Mapped[int] = mapped_column(Integer, default=0)
    entity_ids: Mapped[dict | None] = mapped_column(JSONType) # array of handle/id

    raw_value: Mapped[float] = mapped_column(Float)
    final_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    formula_applied: Mapped[str | None] = mapped_column(Text)

    suggested_rate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("rate_items.id", ondelete="SET NULL"))
    suggested_rate_confidence: Mapped[float | None] = mapped_column(Float)

    classification_method: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    user_override: Mapped[str | None] = mapped_column(String(100))

    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"))
    final_quantity: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

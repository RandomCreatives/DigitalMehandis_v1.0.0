"""Pydantic schemas for the elements module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProjectElementCreate(BaseModel):
    element_code: str = Field(..., max_length=50, examples=["W-001", "C-A1"])
    element_type: str = Field(..., max_length=50, examples=["WALL", "COLUMN"])
    discipline: str = Field(..., max_length=50)
    section: str = Field(..., max_length=50)
    floor_level: str | None = Field(default=None, max_length=50)
    drawing_id: uuid.UUID | None = None
    page_number: int | None = None
    source_type: str = Field(
        default="MANUAL_ENTRY",
        pattern="^(MANUAL_ENTRY|PDF_MEASUREMENT|DXF_LAYER|DXF_BLOCK)$",
    )
    approx_x: float | None = None
    approx_y: float | None = None
    geometry_json: dict | None = None
    material: str | None = Field(default=None, max_length=255)
    specification: dict | None = None


class ProjectElementUpdate(BaseModel):
    element_code: str | None = Field(default=None, max_length=50)
    element_type: str | None = Field(default=None, max_length=50)
    discipline: str | None = None
    section: str | None = None
    floor_level: str | None = None
    material: str | None = None
    specification: dict | None = None
    status: str | None = Field(default=None, pattern="^(ACTIVE|SUPERSEDED|DELETED)$")


class ProjectElementOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    element_code: str
    element_type: str
    discipline: str
    section: str
    floor_level: str | None
    drawing_id: uuid.UUID | None
    page_number: int | None
    source_type: str
    approx_x: float | None
    approx_y: float | None
    geometry_json: Any
    material: str | None
    specification: Any
    status: str
    confidence: float
    created_at: datetime

    model_config = {"from_attributes": True}

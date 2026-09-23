"""Pydantic schemas for the measurements module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MeasurementCreate(BaseModel):
    page_number: int = Field(default=1, ge=1)
    label: str = Field(..., max_length=255)
    measurement_type: str = Field(
        ...,
        pattern="^(LENGTH|AREA|COUNT|VOLUME|DEDUCTION|ANNOTATION)$",
        description="LENGTH | AREA | COUNT | VOLUME | DEDUCTION | ANNOTATION",
    )
    discipline: str = Field(
        ...,
        pattern="^(ARCHITECTURAL|STRUCTURAL|ELECTRICAL|SANITARY)$",
    )
    section: str = Field(
        ...,
        pattern="^(SUBSTRUCTURE|SUPERSTRUCTURE)$",
    )
    element_category: str = Field(..., max_length=100)
    points_json: dict = Field(
        ...,
        description='{"points": [{"x": 100, "y": 200}, ...]}',
    )
    multiplier: float = Field(default=1.0, gt=0)
    color: str = Field(default="#eb6905", max_length=20)
    notes: str | None = None
    project_element_id: uuid.UUID | None = None
    calibration_id: uuid.UUID | None = None


class MeasurementUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    discipline: str | None = None
    section: str | None = None
    element_category: str | None = None
    multiplier: float | None = Field(default=None, gt=0)
    color: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    project_element_id: uuid.UUID | None = None


class MeasurementOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    drawing_id: uuid.UUID
    page_number: int
    calibration_id: uuid.UUID | None
    label: str
    measurement_type: str
    discipline: str
    section: str
    element_category: str
    raw_value: float
    final_value: float
    unit: str
    multiplier: float
    scale_factor_used: float | None
    points_json: Any
    color: str
    project_element_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

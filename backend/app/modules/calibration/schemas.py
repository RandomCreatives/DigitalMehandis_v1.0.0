"""Pydantic schemas for the calibration module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DrawingCalibrationCreate(BaseModel):
    page_number: int = Field(default=1, ge=1)
    reference_name: str | None = Field(default=None, max_length=100, examples=["Grid A-1 to A-2"])
    point_a_x: float = Field(..., description="Canvas pixel X of first point")
    point_a_y: float = Field(..., description="Canvas pixel Y of first point")
    point_b_x: float = Field(..., description="Canvas pixel X of second point")
    point_b_y: float = Field(..., description="Canvas pixel Y of second point")
    real_distance: float = Field(..., gt=0, description="Real-world distance between the two points")
    real_unit: str = Field(default="m", pattern="^(m|mm|cm|ft|in)$")
    floor_level: str | None = Field(default=None, max_length=50, examples=["GF", "1F", "B1"])
    grid_reference: str | None = Field(default=None, max_length=100)
    rotation_degrees: float = Field(default=0.0)

    @model_validator(mode="after")
    def points_must_differ(self) -> DrawingCalibrationCreate:
        dx = self.point_b_x - self.point_a_x
        dy = self.point_b_y - self.point_a_y
        if (dx * dx + dy * dy) < 1:
            raise ValueError("point_a and point_b must be at least 1 pixel apart")
        return self


class DrawingCalibrationOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    drawing_id: uuid.UUID
    page_number: int
    reference_name: str | None
    point_a_x: float
    point_a_y: float
    point_b_x: float
    point_b_y: float
    pixel_distance: float
    real_distance: float
    real_unit: str
    scale_factor: float
    pixels_per_meter: float
    floor_level: str | None
    grid_reference: str | None
    rotation_degrees: float
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}

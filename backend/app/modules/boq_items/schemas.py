"""Pydantic schemas for the boq_items module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class BOQItemCreate(BaseModel):
    item_no: str = Field(..., max_length=20, examples=["2.1.3"])
    section: str = Field(
        ...,
        pattern="^(PRELIMINARIES|SUBSTRUCTURE|SUPERSTRUCTURE|ELECTRICAL|SANITARY|EXTERNAL_WORKS)$",
    )
    trade: str | None = Field(default=None, max_length=100)
    description: str = Field(..., max_length=500)
    unit: str = Field(..., max_length=20)
    quantity: float = Field(..., gt=0)
    rate: float = Field(default=0.0, ge=0)
    waste_factor: float = Field(default=0.0, ge=0, le=100)
    notes: str | None = None
    sort_order: int = Field(default=0, ge=0)


class BOQItemUpdate(BaseModel):
    item_no: str | None = Field(default=None, max_length=20)
    section: str | None = None
    trade: str | None = None
    description: str | None = None
    unit: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    rate: float | None = Field(default=None, ge=0)
    waste_factor: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    sort_order: int | None = None
    is_locked: bool | None = None


class BOQItemOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    item_no: str
    section: str
    trade: str | None
    description: str
    unit: str
    quantity: float
    rate: float
    amount: float
    waste_factor: float
    notes: str | None
    is_locked: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BOQItemSourceCreate(BaseModel):
    suggested_quantity_id: uuid.UUID | None = None
    measurement_id: uuid.UUID | None = None
    project_element_id: uuid.UUID | None = None
    contribution_quantity: float = Field(..., description="Quantity contributed by this source")
    unit: str = Field(..., max_length=20)
    notes: str | None = Field(default=None, max_length=255)


class BOQItemSourceOut(BaseModel):
    id: uuid.UUID
    boq_item_id: uuid.UUID
    suggested_quantity_id: uuid.UUID | None
    measurement_id: uuid.UUID | None
    project_element_id: uuid.UUID | None
    contribution_quantity: float
    unit: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class QuantitySourceOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    suggested_quantity_id: uuid.UUID | None
    boq_item_id: uuid.UUID | None
    source_type: str
    drawing_id: uuid.UUID | None
    page_number: int | None
    measurement_id: uuid.UUID | None
    project_element_id: uuid.UUID | None
    dxf_layer: str | None
    dxf_block_name: str | None
    dxf_entity_id: str | None
    contribution_value: float | None
    contribution_unit: str | None
    confidence: float
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

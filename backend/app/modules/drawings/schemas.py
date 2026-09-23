from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class DrawingOut(BaseModel):
    id: UUID
    project_id: UUID
    filename: str
    file_size_mb: float | None
    category: str | None
    page_count: int | None
    scale: str | None
    title_block_text: str | None
    user_notes: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DrawingUpdate(BaseModel):
    category: str | None = None
    user_notes: str | None = None
    scale: str | None = None

class DXFLayerOut(BaseModel):
    id: UUID
    layer_name: str
    entity_count: int
    classified_as: str | None
    confidence: float
    strategy_used: str | None
    is_ignored: bool
    user_override: str | None

    model_config = {"from_attributes": True}

class DXFBlockOut(BaseModel):
    id: UUID
    block_name: str
    count: int
    classified_as: str | None
    confidence: float

    model_config = {"from_attributes": True}

class DXFLayerUpdate(BaseModel):
    user_override: str | None = None
    is_ignored: bool | None = None

class DXFBlockUpdate(BaseModel):
    user_override: str | None = None # We should add user_override to DXFBlock model too

class ConversionRequest(BaseModel):
    wall_height: float = 3.0
    slab_thickness: float = 0.15
    floor_count: float = 1.0
    beam_width: float = 0.25
    beam_depth: float = 0.5

class QuantitySuggestionOut(BaseModel):
    id: UUID
    project_id: UUID
    drawing_id: UUID
    discipline: str
    task_key: str
    task_label: str | None
    source_layer: str | None
    source_block: str | None
    entity_count: int
    raw_value: float
    final_value: float
    unit: str
    multiplier: float
    formula_applied: str | None
    suggested_rate_id: UUID | None
    confidence: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class QuantitySuggestionReview(BaseModel):
    status: str # APPROVED, REJECTED, EDITED
    final_quantity: float | None = None
    notes: str | None = None

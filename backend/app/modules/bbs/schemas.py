from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class BBSBarCreate(BaseModel):
    member_name: str
    bar_diameter_mm: int
    bar_shape: str
    quantity: int
    clear_length_m: float
    hook_length_mm: int = 0
    bend_deduction_mm: int = 0
    cover_top_mm: int = 50
    cover_bottom_mm: int = 50
    section: str | None = None
    notes: str | None = None
    standard: str = "EBCS_3"


class BBSBarUpdate(BaseModel):
    member_name: str | None = None
    bar_diameter_mm: int | None = None
    bar_shape: str | None = None
    quantity: int | None = None
    clear_length_m: float | None = None
    hook_length_mm: int | None = None
    cover_top_mm: int | None = None
    cover_bottom_mm: int | None = None
    section: str | None = None
    notes: str | None = None


class BBSBarOut(BaseModel):
    id: UUID
    project_id: UUID
    bar_mark: str | None
    member_name: str
    bar_diameter_mm: int
    bar_shape: str
    quantity: int
    clear_length_m: float
    hook_length_mm: int
    cover_top_mm: int
    cover_bottom_mm: int
    lap_length_mm: int | None
    cutting_length_m: float | None = None
    weight_per_unit_kg: float | None = None
    total_weight_kg: float | None = None
    section: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CuttingListItem(BaseModel):
    diameter_mm: int
    cutting_length_m: float
    total_qty: int
    total_weight_kg: float

from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class RateItemBase(BaseModel):
    item_no: Optional[str] = None
    description: str
    unit: str
    direct_cost: float
    currency: str = "ETB"
    region: Optional[str] = None
    source_page: Optional[int] = None
    confidence: float = 1.0

class RateItemCreate(RateItemBase):
    rate_source_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None

class RateItemOut(RateItemBase):
    id: uuid.UUID
    rate_source_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    children: List[RateItemOut] = []

    model_config = ConfigDict(from_attributes=True)

class RateSourceBase(BaseModel):
    title: str
    issuing_authority: Optional[str] = None
    region: Optional[str] = None
    fiscal_year: Optional[str] = None
    quarter: Optional[str] = None

class RateSourceOut(RateSourceBase):
    id: uuid.UUID
    created_at: datetime
    item_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class AddToProjectRequest(BaseModel):
    project_id: uuid.UUID
    rate_item_id: uuid.UUID
    section: str = "SUBSTRUCTURE"
    floor_level: Optional[str] = None

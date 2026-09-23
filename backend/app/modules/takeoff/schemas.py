from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from uuid import UUID

class TakeoffItemCreate(BaseModel):
    description: str
    unit: str
    quantity: float
    section: str | None = "SUBSTRUCTURE"

class TakeoffItemUpdate(BaseModel):
    description: str | None = None
    unit: str | None = None
    quantity: float | None = None
    section: str | None = None

class TakeoffItemOut(BaseModel):
    id: UUID
    project_id: UUID
    description: str
    unit: str
    quantity: float
    section: str | None

    model_config = {"from_attributes": True}

class CanonicalQuantity(BaseModel):
    """Standardized representation of a quantity extracted from any drawing format."""
    source_format: str  # e.g., "PDF", "DXF", "RVT"
    source_id: str      # e.g., Entity ID, Polyline ID, or Page Number
    label: str          # Name of the entity or layer
    quantity_type: str  # "length", "area", "volume", "count"
    value: float
    unit: str
    geometry_data: Optional[Dict[str, Any]] = None  # Original coordinates/paths
    metadata: Optional[Dict[str, Any]] = None       # Layer info, color, etc.

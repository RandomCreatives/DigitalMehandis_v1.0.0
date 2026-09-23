from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class SuggestedQuantityOut(BaseModel):
    id: UUID
    project_id: UUID
    drawing_id: UUID | None
    discipline: str
    element_category: str
    description: str
    quantity_value: float
    quantity_unit: str
    section: str
    source_layer: str | None
    confidence: float
    notes: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SuggestedQuantityReview(BaseModel):
    """Payload for approving / rejecting / editing a suggestion."""
    status: str                        # APPROVED | REJECTED | EDITED
    quantity_value: float | None = None  # Override value if EDITED
    description: str | None = None       # Override description if EDITED
    notes: str | None = None


class FederatedQuantityOut(BaseModel):
    id: UUID
    project_id: UUID
    drawing_id: UUID | None
    discipline: str
    element_category: str
    element_description: str
    quantity_value: float
    quantity_unit: str
    section: str
    source_layer: str | None
    is_verified: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

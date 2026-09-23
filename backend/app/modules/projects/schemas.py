from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    location: str
    description: str | None = None
    code_of_practice: str = "EBCS"
    unit_system: str = "METRIC"
    currency: str = "ETB"


class ProjectUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    description: str | None = None
    code_of_practice: str | None = None
    unit_system: str | None = None
    scale: str | None = None


class ProjectOut(BaseModel):
    id: UUID
    name: str
    location: str
    description: str | None
    code_of_practice: str | None
    unit_system: str
    currency: str
    scale: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

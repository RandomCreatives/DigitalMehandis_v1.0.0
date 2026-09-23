from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class BOQLine(BaseModel):
    item_number: int
    description: str
    unit: str
    quantity: float
    rate: float
    amount: float
    notes: str = ""


class BOQResult(BaseModel):
    project_id: UUID
    section: str
    lines: list[BOQLine]
    total_amount: float
    currency: str


class BOQOutputOut(BaseModel):
    id: UUID
    project_id: UUID
    section: str
    generated_at: datetime
    total_amount: float | None
    currency: str
    pdf_path: str | None
    excel_path: str | None

    model_config = {"from_attributes": True}


class RateCreate(BaseModel):
    item_code: str | None = None
    description: str
    unit: str
    rate_per_unit: float
    rate_source: str | None = None
    region: str | None = None


class RateOut(BaseModel):
    id: UUID
    item_code: str | None
    description: str
    unit: str
    rate_per_unit: float
    rate_source: str | None
    region: str | None

    model_config = {"from_attributes": True}

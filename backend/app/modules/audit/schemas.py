"""Pydantic schemas for the audit module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AuditLogOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    user_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: str | None
    description: str | None
    old_value: Any
    new_value: Any
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

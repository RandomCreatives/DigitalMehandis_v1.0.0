"""Audit Log API — read-only access to the project audit trail."""
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.audit.models import AuditLog
from app.core.deps import get_current_user

router = APIRouter(tags=["audit"])


class AuditLogOut(BaseModel):
    id: UUID
    project_id: UUID | None
    user_id: UUID | None
    action: str
    entity_type: str | None
    entity_id: str | None
    description: str | None
    created_at: Any

    model_config = {"from_attributes": True}


@router.get("/projects/{project_id}/audit-log", response_model=list[AuditLogOut])
async def get_audit_log(
    project_id: UUID,
    action: str | None = None,
    limit: int = Query(default=50, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        from fastapi import HTTPException
        raise HTTPException(404, "Project not found")

    stmt = select(AuditLog).where(AuditLog.project_id == project_id)
    if action:
        stmt = stmt.where(AuditLog.action == action.upper())
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()

"""
Project Elements API — simple element identity for Phase 2.

POST   /projects/{id}/elements          — create element
GET    /projects/{id}/elements          — list elements
GET    /projects/{id}/elements/{id}     — get element with measurements
PUT    /projects/{id}/elements/{id}     — update element
DELETE /projects/{id}/elements/{id}     — delete element
"""
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.elements.models import ProjectElement
from app.modules.measurements.models import Measurement
from app.modules.audit.models import AuditLog
from app.core.deps import get_current_user

router = APIRouter(tags=["elements"])

ELEMENT_TYPES = {
    "WALL", "COLUMN", "BEAM", "SLAB", "FOOTING", "SHEAR_WALL",
    "TIE_BEAM", "PLINTH_BEAM", "DOOR", "WINDOW", "STAIR", "ROOF",
    "FLOOR", "CEILING", "ROOM",
    "SOCKET", "SWITCH", "LIGHT_FIXTURE", "PANEL", "CONDUIT",
    "TOILET", "BASIN", "SINK", "SHOWER", "FLOOR_DRAIN", "PIPE",
    "OTHER",
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class ElementCreate(BaseModel):
    element_code: str
    element_type: str
    discipline: str
    section: str
    floor_level: str | None = None
    drawing_id: UUID | None = None
    page_number: int | None = None
    source_type: str = "MANUAL_ENTRY"
    approx_x: float | None = None
    approx_y: float | None = None
    geometry_json: dict | None = None
    material: str | None = None
    specification: dict | None = None


class ElementUpdate(BaseModel):
    element_code: str | None = None
    element_type: str | None = None
    discipline: str | None = None
    section: str | None = None
    floor_level: str | None = None
    material: str | None = None
    specification: dict | None = None
    status: str | None = None


class ElementOut(BaseModel):
    id: UUID
    project_id: UUID
    element_code: str
    element_type: str
    discipline: str
    section: str
    floor_level: str | None
    drawing_id: UUID | None
    page_number: int | None
    source_type: str
    approx_x: float | None
    approx_y: float | None
    geometry_json: dict | None
    material: str | None
    specification: dict | None
    status: str
    confidence: float
    created_at: Any

    model_config = {"from_attributes": True}


class ElementDetailOut(ElementOut):
    measurements: list[dict] = []
    measurement_count: int = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_project(project_id: UUID, user: User, db: AsyncSession) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/elements",
    response_model=ElementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_element(
    project_id: UUID,
    payload: ElementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)

    if payload.element_type.upper() not in ELEMENT_TYPES:
        raise HTTPException(400, f"Unknown element_type '{payload.element_type}'")

    elem = ProjectElement(
        project_id=project_id,
        element_code=payload.element_code,
        element_type=payload.element_type.upper(),
        discipline=payload.discipline.upper(),
        section=payload.section.upper(),
        floor_level=payload.floor_level,
        drawing_id=payload.drawing_id,
        page_number=payload.page_number,
        source_type=payload.source_type,
        approx_x=payload.approx_x,
        approx_y=payload.approx_y,
        geometry_json=payload.geometry_json,
        material=payload.material,
        specification=payload.specification,
        created_by=user.id,
    )
    db.add(elem)

    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="ELEMENT_CREATED",
        entity_type="ProjectElement",
        description=f"Element {payload.element_code} ({payload.element_type}) created",
    ))

    await db.commit()
    await db.refresh(elem)
    return elem


@router.get(
    "/projects/{project_id}/elements",
    response_model=list[ElementOut],
)
async def list_elements(
    project_id: UUID,
    element_type: str | None = None,
    discipline: str | None = None,
    section: str | None = None,
    floor_level: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    stmt = select(ProjectElement).where(
        ProjectElement.project_id == project_id,
        ProjectElement.status == "ACTIVE",
    )
    if element_type:
        stmt = stmt.where(ProjectElement.element_type == element_type.upper())
    if discipline:
        stmt = stmt.where(ProjectElement.discipline == discipline.upper())
    if section:
        stmt = stmt.where(ProjectElement.section == section.upper())
    if floor_level:
        stmt = stmt.where(ProjectElement.floor_level == floor_level)
    result = await db.execute(stmt.order_by(ProjectElement.element_code))
    return result.scalars().all()


@router.get(
    "/projects/{project_id}/elements/{element_id}",
    response_model=ElementDetailOut,
)
async def get_element(
    project_id: UUID,
    element_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get element with all linked measurements."""
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.id == element_id,
            ProjectElement.project_id == project_id,
        )
    )
    elem = result.scalar_one_or_none()
    if not elem:
        raise HTTPException(404, "Element not found")

    # Get linked measurements
    m_result = await db.execute(
        select(Measurement).where(Measurement.project_element_id == element_id)
    )
    measurements = m_result.scalars().all()

    out = ElementDetailOut.model_validate(elem)
    out.measurements = [
        {
            "id": str(m.id),
            "label": m.label,
            "type": m.measurement_type,
            "value": m.final_value,
            "unit": m.unit,
            "drawing_id": str(m.drawing_id),
            "page_number": m.page_number,
        }
        for m in measurements
    ]
    out.measurement_count = len(measurements)
    return out


@router.put(
    "/projects/{project_id}/elements/{element_id}",
    response_model=ElementOut,
)
async def update_element(
    project_id: UUID,
    element_id: UUID,
    payload: ElementUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.id == element_id,
            ProjectElement.project_id == project_id,
        )
    )
    elem = result.scalar_one_or_none()
    if not elem:
        raise HTTPException(404, "Element not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "element_type" and value:
            value = value.upper()
        setattr(elem, field, value)

    await db.commit()
    await db.refresh(elem)
    return elem


@router.delete(
    "/projects/{project_id}/elements/{element_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_element(
    project_id: UUID,
    element_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.id == element_id,
            ProjectElement.project_id == project_id,
        )
    )
    elem = result.scalar_one_or_none()
    if not elem:
        raise HTTPException(404, "Element not found")
    elem.status = "DELETED"
    await db.commit()

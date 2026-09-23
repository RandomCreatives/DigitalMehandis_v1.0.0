"""
Measurements API — persistent canvas measurements with geometry and source tracing.

POST   /projects/{id}/drawings/{id}/measurements       — create measurement
GET    /projects/{id}/drawings/{id}/measurements       — list measurements for drawing
GET    /projects/{id}/measurements                     — list all measurements for project
PUT    /projects/{id}/measurements/{id}                — update measurement
DELETE /projects/{id}/measurements/{id}                — delete measurement
POST   /projects/{id}/measurements/{id}/create-quantity — promote to suggested quantity
POST   /projects/{id}/measurements/{id}/link-element   — link to project element
"""
import math
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.modules.drawings.models import Drawing
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.takeoff.models import SuggestedQuantity
from app.modules.measurements.models import Measurement
from app.modules.calibration.models import DrawingCalibration
from app.modules.elements.models import ProjectElement
from app.modules.boq_items.models import QuantitySource
from app.modules.audit.models import AuditLog
from app.core.deps import get_current_user

router = APIRouter(tags=["measurements"])

DISCIPLINES = {"ARCHITECTURAL", "STRUCTURAL", "ELECTRICAL", "SANITARY"}
SECTIONS = {"SUBSTRUCTURE", "SUPERSTRUCTURE"}
MEASUREMENT_TYPES = {"LENGTH", "AREA", "COUNT", "VOLUME", "DEDUCTION", "ANNOTATION"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class MeasurementCreate(BaseModel):
    page_number: int = 1
    label: str
    measurement_type: str          # LENGTH | AREA | COUNT | VOLUME | DEDUCTION
    discipline: str
    section: str
    element_category: str
    points_json: dict              # {"points": [{"x": 100, "y": 200}, ...]}
    multiplier: float = 1.0
    color: str = "#eb6905"
    notes: str | None = None
    project_element_id: UUID | None = None
    calibration_id: UUID | None = None


class MeasurementUpdate(BaseModel):
    label: str | None = None
    discipline: str | None = None
    section: str | None = None
    element_category: str | None = None
    multiplier: float | None = None
    color: str | None = None
    notes: str | None = None
    project_element_id: UUID | None = None


class MeasurementOut(BaseModel):
    id: UUID
    project_id: UUID
    drawing_id: UUID
    page_number: int
    calibration_id: UUID | None
    label: str
    measurement_type: str
    discipline: str
    section: str
    element_category: str
    raw_value: float
    final_value: float
    unit: str
    multiplier: float
    scale_factor_used: float | None
    points_json: dict
    color: str
    project_element_id: UUID | None
    notes: str | None
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class PromoteToQuantityPayload(BaseModel):
    description: str | None = None  # defaults to measurement label


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_project(project_id: UUID, user: User, db: AsyncSession) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")


def _compute_measurement(
    measurement_type: str,
    points: list[dict],
    calibration: DrawingCalibration | None,
    multiplier: float,
) -> tuple[float, float, str, float | None]:
    """
    Compute raw_value, final_value, unit, and scale_factor_used from canvas points.
    Returns (raw_value, final_value, unit, scale_factor_used).
    """
    scale = calibration.scale_factor if calibration else None  # meters per pixel

    if measurement_type == "LENGTH":
        # Sum of segment lengths in pixels
        raw = 0.0
        for i in range(len(points) - 1):
            dx = points[i+1]["x"] - points[i]["x"]
            dy = points[i+1]["y"] - points[i]["y"]
            raw += math.sqrt(dx*dx + dy*dy)
        final = (raw * scale * multiplier) if scale else raw * multiplier
        unit = "m" if scale else "px"

    elif measurement_type == "AREA":
        # Shoelace formula for polygon area in pixels²
        n = len(points)
        raw = 0.0
        for i in range(n):
            j = (i + 1) % n
            raw += points[i]["x"] * points[j]["y"]
            raw -= points[j]["x"] * points[i]["y"]
        raw = abs(raw) / 2.0
        final = (raw * scale * scale * multiplier) if scale else raw * multiplier
        unit = "m²" if scale else "px²"

    elif measurement_type == "COUNT":
        raw = float(len(points))
        final = raw * multiplier
        unit = "Nr"

    elif measurement_type == "VOLUME":
        # Expects area measurement + thickness in notes or multiplier
        # For now: area × multiplier (multiplier = thickness in m)
        n = len(points)
        area_px = 0.0
        for i in range(n):
            j = (i + 1) % n
            area_px += points[i]["x"] * points[j]["y"]
            area_px -= points[j]["x"] * points[i]["y"]
        area_px = abs(area_px) / 2.0
        raw = area_px
        final = (area_px * scale * scale * multiplier) if scale else area_px * multiplier
        unit = "m³" if scale else "px³"

    elif measurement_type == "DEDUCTION":
        # Same as AREA but negative contribution
        n = len(points)
        raw = 0.0
        for i in range(n):
            j = (i + 1) % n
            raw += points[i]["x"] * points[j]["y"]
            raw -= points[j]["x"] * points[i]["y"]
        raw = abs(raw) / 2.0
        final = -(raw * scale * scale * multiplier) if scale else -(raw * multiplier)
        unit = "m²" if scale else "px²"

    else:  # ANNOTATION
        raw = 0.0
        final = 0.0
        unit = ""

    return round(raw, 6), round(final, 4), unit, scale


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/drawings/{drawing_id}/measurements",
    response_model=MeasurementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_measurement(
    project_id: UUID,
    drawing_id: UUID,
    payload: MeasurementCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save a canvas measurement with geometry.
    Automatically computes real-world value using active calibration.
    """
    await _check_project(project_id, user, db)

    # Validate drawing belongs to project
    result = await db.execute(
        select(Drawing).where(Drawing.id == drawing_id, Drawing.project_id == project_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Drawing not found")

    if payload.measurement_type.upper() not in MEASUREMENT_TYPES:
        raise HTTPException(400, f"Invalid measurement_type. Must be one of {MEASUREMENT_TYPES}")
    if payload.discipline.upper() not in DISCIPLINES:
        raise HTTPException(400, f"Invalid discipline. Must be one of {DISCIPLINES}")
    if payload.section.upper() not in SECTIONS:
        raise HTTPException(400, f"Invalid section. Must be one of {SECTIONS}")

    # Get calibration
    calibration = None
    if payload.calibration_id:
        result = await db.execute(
            select(DrawingCalibration).where(DrawingCalibration.id == payload.calibration_id)
        )
        calibration = result.scalar_one_or_none()
    else:
        # Use active calibration for this drawing/page
        result = await db.execute(
            select(DrawingCalibration).where(
                DrawingCalibration.drawing_id == drawing_id,
                DrawingCalibration.page_number == payload.page_number,
                DrawingCalibration.is_active == True,
            )
        )
        calibration = result.scalar_one_or_none()

    points = payload.points_json.get("points", [])
    if not points and payload.measurement_type != "ANNOTATION":
        raise HTTPException(400, "points_json must contain a 'points' array")

    raw_value, final_value, unit, scale_used = _compute_measurement(
        payload.measurement_type.upper(), points, calibration, payload.multiplier
    )

    m = Measurement(
        project_id=project_id,
        drawing_id=drawing_id,
        page_number=payload.page_number,
        calibration_id=calibration.id if calibration else None,
        label=payload.label,
        measurement_type=payload.measurement_type.upper(),
        discipline=payload.discipline.upper(),
        section=payload.section.upper(),
        element_category=payload.element_category.upper(),
        raw_value=raw_value,
        final_value=final_value,
        unit=unit,
        multiplier=payload.multiplier,
        scale_factor_used=scale_used,
        points_json=payload.points_json,
        color=payload.color,
        project_element_id=payload.project_element_id,
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(m)

    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="MEASUREMENT_CREATED",
        entity_type="Measurement",
        description=f"{payload.measurement_type} measurement '{payload.label}': {final_value} {unit}",
    ))

    await db.commit()
    await db.refresh(m)
    return m


@router.get(
    "/projects/{project_id}/drawings/{drawing_id}/measurements",
    response_model=list[MeasurementOut],
)
async def list_drawing_measurements(
    project_id: UUID,
    drawing_id: UUID,
    page_number: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    stmt = select(Measurement).where(
        Measurement.project_id == project_id,
        Measurement.drawing_id == drawing_id,
    )
    if page_number is not None:
        stmt = stmt.where(Measurement.page_number == page_number)
    result = await db.execute(stmt.order_by(Measurement.created_at))
    return result.scalars().all()


@router.get(
    "/projects/{project_id}/measurements",
    response_model=list[MeasurementOut],
)
async def list_project_measurements(
    project_id: UUID,
    discipline: str | None = None,
    section: str | None = None,
    element_category: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    stmt = select(Measurement).where(Measurement.project_id == project_id)
    if discipline:
        stmt = stmt.where(Measurement.discipline == discipline.upper())
    if section:
        stmt = stmt.where(Measurement.section == section.upper())
    if element_category:
        stmt = stmt.where(Measurement.element_category == element_category.upper())
    result = await db.execute(stmt.order_by(Measurement.created_at))
    return result.scalars().all()


@router.put(
    "/projects/{project_id}/measurements/{measurement_id}",
    response_model=MeasurementOut,
)
async def update_measurement(
    project_id: UUID,
    measurement_id: UUID,
    payload: MeasurementUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(Measurement).where(
            Measurement.id == measurement_id,
            Measurement.project_id == project_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Measurement not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(m, field, value)

    await db.commit()
    await db.refresh(m)
    return m


@router.delete(
    "/projects/{project_id}/measurements/{measurement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_measurement(
    project_id: UUID,
    measurement_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(Measurement).where(
            Measurement.id == measurement_id,
            Measurement.project_id == project_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Measurement not found")
    await db.delete(m)
    await db.commit()


@router.post(
    "/projects/{project_id}/measurements/{measurement_id}/create-quantity",
    status_code=status.HTTP_201_CREATED,
)
async def promote_to_quantity(
    project_id: UUID,
    measurement_id: UUID,
    payload: PromoteToQuantityPayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote a measurement to a SuggestedQuantity with full source traceability.
    The quantity enters the approval workflow before reaching the BOQ.
    """
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(Measurement).where(
            Measurement.id == measurement_id,
            Measurement.project_id == project_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Measurement not found")

    description = payload.description or m.label

    sq = SuggestedQuantity(
        project_id=project_id,
        drawing_id=m.drawing_id,
        discipline=m.discipline,
        element_category=m.element_category,
        description=description,
        quantity_value=abs(m.final_value),
        quantity_unit=m.unit,
        section=m.section,
        source_layer=f"Page {m.page_number}",
        confidence=0.95,  # User-measured = high confidence
        notes=m.notes,
        status="PENDING",
    )
    db.add(sq)
    await db.flush()

    # Create quantity source record (the traceability link)
    qs = QuantitySource(
        project_id=project_id,
        suggested_quantity_id=sq.id,
        source_type="PDF_MEASUREMENT",
        drawing_id=m.drawing_id,
        page_number=m.page_number,
        measurement_id=m.id,
        project_element_id=m.project_element_id,
        contribution_value=abs(m.final_value),
        contribution_unit=m.unit,
        confidence=0.95,
    )
    db.add(qs)

    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="QUANTITY_CREATED_FROM_MEASUREMENT",
        entity_type="SuggestedQuantity",
        description=f"Quantity '{description}' created from measurement '{m.label}'",
    ))

    await db.commit()
    await db.refresh(sq)

    return {
        "suggested_quantity_id": str(sq.id),
        "description": description,
        "quantity_value": float(sq.quantity_value),
        "unit": sq.quantity_unit,
        "source_measurement_id": str(m.id),
        "message": "Quantity created and pending review",
    }


@router.post(
    "/projects/{project_id}/measurements/{measurement_id}/link-element",
)
async def link_to_element(
    project_id: UUID,
    measurement_id: UUID,
    element_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link a measurement to a project element."""
    await _check_project(project_id, user, db)

    result = await db.execute(
        select(Measurement).where(
            Measurement.id == measurement_id,
            Measurement.project_id == project_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "Measurement not found")

    result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.id == element_id,
            ProjectElement.project_id == project_id,
        )
    )
    elem = result.scalar_one_or_none()
    if not elem:
        raise HTTPException(404, "Project element not found")

    m.project_element_id = element_id
    await db.commit()

    return {"message": f"Measurement linked to element {elem.element_code}"}

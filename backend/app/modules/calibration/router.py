"""
Drawing Calibration API
POST /projects/{id}/drawings/{id}/calibrations  — create calibration
GET  /projects/{id}/drawings/{id}/calibrations  — list calibrations
GET  /projects/{id}/drawings/{id}/calibrations/active — get active calibration
DELETE /projects/{id}/calibrations/{id}         — delete calibration
"""
import math
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.modules.drawings.models import Drawing
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.calibration.models import DrawingCalibration
from app.modules.audit.models import AuditLog
from app.core.deps import get_current_user

router = APIRouter(tags=["calibration"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CalibrationCreate(BaseModel):
    page_number: int = 1
    reference_name: str | None = None
    point_a_x: float
    point_a_y: float
    point_b_x: float
    point_b_y: float
    real_distance: float
    real_unit: str = "m"
    floor_level: str | None = None
    grid_reference: str | None = None
    rotation_degrees: float = 0.0


class CalibrationOut(BaseModel):
    id: UUID
    drawing_id: UUID
    page_number: int
    reference_name: str | None
    point_a_x: float
    point_a_y: float
    point_b_x: float
    point_b_y: float
    pixel_distance: float
    real_distance: float
    real_unit: str
    scale_factor: float
    pixels_per_meter: float
    floor_level: str | None
    grid_reference: str | None
    is_active: bool

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_project_drawing(
    project_id: UUID, drawing_id: UUID, user: User, db: AsyncSession
) -> Drawing:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    result = await db.execute(
        select(Drawing).where(Drawing.id == drawing_id, Drawing.project_id == project_id)
    )
    drawing = result.scalar_one_or_none()
    if not drawing:
        raise HTTPException(404, "Drawing not found")
    return drawing


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/drawings/{drawing_id}/calibrations",
    response_model=CalibrationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_calibration(
    project_id: UUID,
    drawing_id: UUID,
    payload: CalibrationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a scale calibration for a drawing page.
    User provides two canvas points and the real-world distance between them.
    System computes scale_factor and pixels_per_meter.
    """
    await _check_project_drawing(project_id, drawing_id, user, db)

    # Compute pixel distance
    dx = payload.point_b_x - payload.point_a_x
    dy = payload.point_b_y - payload.point_a_y
    pixel_distance = math.sqrt(dx * dx + dy * dy)

    if pixel_distance < 1:
        raise HTTPException(400, "Points are too close together — select two distinct points")

    # Convert real distance to meters
    unit_to_m = {"m": 1.0, "mm": 0.001, "cm": 0.01, "ft": 0.3048, "in": 0.0254}
    real_distance_m = payload.real_distance * unit_to_m.get(payload.real_unit, 1.0)

    if real_distance_m <= 0:
        raise HTTPException(400, "Real distance must be greater than zero")

    scale_factor = real_distance_m / pixel_distance  # meters per pixel
    pixels_per_meter = pixel_distance / real_distance_m

    # Deactivate previous calibrations for this drawing/page
    prev = await db.execute(
        select(DrawingCalibration).where(
            DrawingCalibration.drawing_id == drawing_id,
            DrawingCalibration.page_number == payload.page_number,
            DrawingCalibration.is_active == True,
        )
    )
    for old in prev.scalars().all():
        old.is_active = False

    cal = DrawingCalibration(
        project_id=project_id,
        drawing_id=drawing_id,
        page_number=payload.page_number,
        reference_name=payload.reference_name,
        point_a_x=payload.point_a_x,
        point_a_y=payload.point_a_y,
        point_b_x=payload.point_b_x,
        point_b_y=payload.point_b_y,
        pixel_distance=pixel_distance,
        real_distance=payload.real_distance,
        real_unit=payload.real_unit,
        scale_factor=scale_factor,
        pixels_per_meter=pixels_per_meter,
        floor_level=payload.floor_level,
        grid_reference=payload.grid_reference,
        rotation_degrees=payload.rotation_degrees,
        is_active=True,
        created_by=user.id,
    )
    db.add(cal)

    # Audit log
    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="DRAWING_CALIBRATED",
        entity_type="DrawingCalibration",
        description=f"Drawing calibrated: 1px = {scale_factor*1000:.3f}mm (scale factor {scale_factor:.6f})",
    ))

    await db.commit()
    await db.refresh(cal)
    return cal


@router.get(
    "/projects/{project_id}/drawings/{drawing_id}/calibrations",
    response_model=list[CalibrationOut],
)
async def list_calibrations(
    project_id: UUID,
    drawing_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project_drawing(project_id, drawing_id, user, db)
    result = await db.execute(
        select(DrawingCalibration)
        .where(DrawingCalibration.drawing_id == drawing_id)
        .order_by(DrawingCalibration.page_number)
    )
    return result.scalars().all()


@router.get(
    "/projects/{project_id}/drawings/{drawing_id}/calibrations/active",
    response_model=CalibrationOut | None,
)
async def get_active_calibration(
    project_id: UUID,
    drawing_id: UUID,
    page_number: int = 1,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project_drawing(project_id, drawing_id, user, db)
    result = await db.execute(
        select(DrawingCalibration).where(
            DrawingCalibration.drawing_id == drawing_id,
            DrawingCalibration.page_number == page_number,
            DrawingCalibration.is_active == True,
        )
    )
    return result.scalar_one_or_none()


@router.delete(
    "/projects/{project_id}/calibrations/{calibration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_calibration(
    project_id: UUID,
    calibration_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DrawingCalibration).where(
            DrawingCalibration.id == calibration_id,
            DrawingCalibration.project_id == project_id,
        )
    )
    cal = result.scalar_one_or_none()
    if not cal:
        raise HTTPException(404, "Calibration not found")
    await db.delete(cal)
    await db.commit()

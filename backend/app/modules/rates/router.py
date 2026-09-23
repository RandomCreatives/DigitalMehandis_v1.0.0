from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.rates.models import Rate
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.boq.schemas import RateOut
from app.core.deps import get_current_user
from app.modules.boq.exporters import export_rates_excel
from pydantic import BaseModel
from uuid import UUID
from typing import Any
import openpyxl
import io

router = APIRouter(tags=["rates"])


class RateCreate(BaseModel):
    item_code: str | None = None
    description: str
    unit: str
    rate_per_unit: float
    rate_source: str | None = None
    region: str | None = "Addis Ababa"


class RateUpdate(BaseModel):
    description: str | None = None
    unit: str | None = None
    rate_per_unit: float | None = None
    rate_source: str | None = None
    region: str | None = None


class RateOutFull(BaseModel):
    id: UUID
    project_id: UUID | None
    item_code: str | None
    description: str
    unit: str
    rate_per_unit: float
    rate_source: str | None
    region: str | None
    created_at: Any
    model_config = {"from_attributes": True}


async def _check_project(project_id: UUID, user: User, db: AsyncSession) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")


# ── Global rate database (read-only) ─────────────────────────────────────────

@router.get("/rates/database", response_model=list[RateOutFull])
async def get_global_rates(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the pre-loaded global rate database (project_id IS NULL)."""
    result = await db.execute(select(Rate).where(Rate.project_id.is_(None)).order_by(Rate.item_code))
    return result.scalars().all()


# ── Project-specific rate library ─────────────────────────────────────────────

@router.get("/projects/{project_id}/rates", response_model=list[RateOutFull])
async def list_project_rates(
    project_id: UUID,
    region: str | None = None,
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all rates for a project (project-specific + global)."""
    await _check_project(project_id, user, db)
    stmt = select(Rate).where(
        (Rate.project_id == project_id) | (Rate.project_id.is_(None))
    )
    if region:
        stmt = stmt.where(Rate.region == region)
    if search:
        stmt = stmt.where(Rate.description.ilike(f"%{search}%"))
    result = await db.execute(stmt.order_by(Rate.item_code))
    return result.scalars().all()


@router.post(
    "/projects/{project_id}/rates",
    response_model=RateOutFull,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_rate(
    project_id: UUID,
    payload: RateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a project-specific rate."""
    await _check_project(project_id, user, db)
    rate = Rate(
        project_id=project_id,
        item_code=payload.item_code,
        description=payload.description,
        unit=payload.unit,
        rate_per_unit=payload.rate_per_unit,
        rate_source=payload.rate_source,
        region=payload.region,
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.put("/projects/{project_id}/rates/{rate_id}", response_model=RateOutFull)
async def update_project_rate(
    project_id: UUID,
    rate_id: UUID,
    payload: RateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(Rate).where(Rate.id == rate_id, Rate.project_id == project_id)
    )
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(404, "Rate not found or is a global rate (cannot edit)")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rate, field, value)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.delete("/projects/{project_id}/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_rate(
    project_id: UUID,
    rate_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(Rate).where(Rate.id == rate_id, Rate.project_id == project_id)
    )
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(404, "Rate not found or is a global rate (cannot delete)")
    await db.delete(rate)
    await db.commit()


@router.get("/projects/{project_id}/rates/export-excel")
async def export_project_rates_to_excel(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _check_project(project_id, user, db)
    result = await db.execute(
        select(Rate).where(Rate.project_id == project_id).order_by(Rate.item_code)
    )
    rates = result.scalars().all()
    rate_dicts = [
        {
            "item_code": r.item_code,
            "description": r.description,
            "unit": r.unit,
            "rate_per_unit": float(r.rate_per_unit),
            "rate_source": r.rate_source,
            "region": r.region,
        }
        for r in rates
    ]
    xlsx_bytes = export_rates_excel(rate_dicts, project.name)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Rates_{project.name}.xlsx"'},
    )


@router.post("/projects/{project_id}/rates/import-excel", status_code=status.HTTP_201_CREATED)
async def import_project_rates_from_excel(
    project_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Invalid file format. Please upload an Excel file.")

    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active

    imported_count = 0
    # Expected headers: Item Code, Description, Unit, Rate (ETB), Source, Region
    # Skip rows until we find headers or data. Let's assume headers are on row 4 as per export.
    for row in ws.iter_rows(min_row=5, values_only=True):
        if not row or not any(row):
            continue

        # Robust column unpacking
        item_code = row[0] if len(row) > 0 else None
        description = row[1] if len(row) > 1 else None
        unit = row[2] if len(row) > 2 else "Nr"
        rate_val = row[3] if len(row) > 3 else None
        source = row[4] if len(row) > 4 else "Imported"
        region = row[5] if len(row) > 5 else "Addis Ababa"

        if not description or rate_val is None:
            continue

        try:
            rate_numeric = float(rate_val)
        except (ValueError, TypeError):
            continue

        rate = Rate(
            project_id=project_id,
            item_code=str(item_code) if item_code else None,
            description=str(description),
            unit=str(unit) if unit else "Nr",
            rate_per_unit=rate_numeric,
            rate_source=str(source) if source else "Imported",
            region=str(region) if region else "Addis Ababa",
        )
        db.add(rate)
        imported_count += 1

    await db.commit()
    return {"message": f"Successfully imported {imported_count} rates", "imported": imported_count}


# ── BBS → BOQ feed (Federation Workflow) ──────────────────────────────────────

@router.post("/projects/{project_id}/bbs/sync-to-boq", status_code=status.HTTP_201_CREATED)
async def bbs_sync_to_boq(
    project_id: UUID,
    section: str = "SUBSTRUCTURE",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync BBS steel totals to Federated Quantities.
    Groups by diameter and creates PENDING suggested quantities.
    Following Phase 2 federation workflow: Suggestions -> Review -> BOQ.
    """
    from app.modules.bbs.models import BBSBar
    from app.modules.takeoff.models import SuggestedQuantity
    from app.modules.audit.models import AuditLog
    from app.modules.bbs.calculator import BBSCalculator

    await _check_project(project_id, user, db)

    # Get all bars for this project/section
    bars_result = await db.execute(
        select(BBSBar).where(
            BBSBar.project_id == project_id,
            BBSBar.section == section.upper(),
        )
    )
    bars = bars_result.scalars().all()
    if not bars:
        return {"message": "No BBS bars found for this section", "created": 0}

    # Group by diameter
    by_dia: dict[int, float] = {}
    for bar in bars:
        raw = {
            "bar_shape": bar.bar_shape,
            "clear_length_m": float(bar.clear_length_m),
            "bar_diameter_mm": bar.bar_diameter_mm,
            "hook_length_mm": bar.hook_length_mm or 0,
            "cover_top_mm": bar.cover_top_mm or 50,
            "cover_bottom_mm": bar.cover_bottom_mm or 50,
            "quantity": bar.quantity,
        }
        enriched = BBSCalculator.enrich_bar(raw)
        by_dia[bar.bar_diameter_mm] = by_dia.get(bar.bar_diameter_mm, 0.0) + enriched["total_weight_kg"]

    # Delete existing PENDING suggestions from BBS to avoid duplicates
    # Identification by notes: "Source: BBS sync"
    # await db.execute(
    #     delete(SuggestedQuantity).where(
    #         SuggestedQuantity.project_id == project_id,
    #         SuggestedQuantity.section == section.upper(),
    #         SuggestedQuantity.notes.like("%Source: BBS sync%"),
    #         SuggestedQuantity.status == "PENDING"
    #     )
    # )

    created_count = 0
    for dia, total_kg in sorted(by_dia.items()):
        # Map to MoUDC classification (Example: 2400 for Steel reinforcement)
        moudc_code = "2411" if dia <= 8 else "2412"
        sq = SuggestedQuantity(
            project_id=project_id,
            discipline="STRUCTURAL",
            element_category="REINFORCEMENT",
            description=f"High yield deformed bar Ø{dia}mm (MoUDC {moudc_code})",
            quantity_value=round(total_kg, 2),
            quantity_unit="kg",
            section=section.upper(),
            source_layer="BBS",
            confidence=1.0,  # Computed from BBS = high confidence
            notes=f"Source: BBS sync — {section}",
            status="PENDING",
        )
        db.add(sq)
        created_count += 1

    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="BBS_SYNCED_TO_SUGGESTIONS",
        entity_type="SuggestedQuantity",
        description=f"BBS steel totals synced to suggestions: {created_count} groups, {section}",
    ))

    await db.commit()
    return {
        "message": f"Synced {created_count} diameter groups to Suggested Quantities",
        "count": created_count,
        "section": section,
    }

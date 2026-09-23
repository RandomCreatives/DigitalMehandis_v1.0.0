from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.bbs.models import BBSBar
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.takeoff.models import SuggestedQuantity
from app.modules.bbs.schemas import BBSBarCreate, BBSBarUpdate, BBSBarOut, CuttingListItem
from app.core.deps import get_current_user
from app.modules.bbs.calculator import BBSCalculator

router = APIRouter(prefix="/projects/{project_id}/bbs", tags=["bbs"])


async def _check_project(project_id: UUID, user: User, db: AsyncSession):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")


def _bar_mark(index: int) -> str:
    return f"B{index}"


def _enrich(bar: BBSBar, standard: str = "EBCS_3") -> dict:
    raw = {
        "bar_shape": bar.bar_shape,
        "clear_length_m": float(bar.clear_length_m),
        "bar_diameter_mm": bar.bar_diameter_mm,
        "hook_length_mm": bar.hook_length_mm or 0,
        "cover_top_mm": bar.cover_top_mm or 50,
        "cover_bottom_mm": bar.cover_bottom_mm or 50,
        "quantity": bar.quantity,
    }
    enriched = BBSCalculator.enrich_bar(raw, standard)
    return {
        "id": bar.id,
        "project_id": bar.project_id,
        "bar_mark": bar.bar_mark,
        "member_name": bar.member_name,
        "bar_diameter_mm": bar.bar_diameter_mm,
        "bar_shape": bar.bar_shape,
        "quantity": bar.quantity,
        "clear_length_m": float(bar.clear_length_m),
        "hook_length_mm": bar.hook_length_mm,
        "cover_top_mm": bar.cover_top_mm,
        "cover_bottom_mm": bar.cover_bottom_mm,
        "lap_length_mm": enriched["lap_length_mm"],
        "cutting_length_m": enriched["cutting_length_m"],
        "weight_per_unit_kg": enriched["weight_per_unit_kg"],
        "total_weight_kg": enriched["total_weight_kg"],
        "section": bar.section,
        "notes": bar.notes,
        "created_at": bar.created_at,
    }


@router.get("", response_model=list[BBSBarOut])
async def list_bars(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(BBSBar).where(BBSBar.project_id == project_id))
    bars = result.scalars().all()
    return [_enrich(b) for b in bars]


@router.post("", response_model=BBSBarOut, status_code=status.HTTP_201_CREATED)
async def add_bar(project_id: UUID, payload: BBSBarCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)

    # Auto-generate bar mark
    count_result = await db.execute(select(BBSBar).where(BBSBar.project_id == project_id))
    count = len(count_result.scalars().all())

    lap = BBSCalculator.calculate_lap_length(payload.bar_diameter_mm, payload.standard)

    bar = BBSBar(
        project_id=project_id,
        bar_mark=_bar_mark(count + 1),
        member_name=payload.member_name,
        bar_diameter_mm=payload.bar_diameter_mm,
        bar_shape=payload.bar_shape,
        quantity=payload.quantity,
        clear_length_m=payload.clear_length_m,
        hook_length_mm=payload.hook_length_mm,
        bend_deduction_mm=payload.bend_deduction_mm,
        cover_top_mm=payload.cover_top_mm,
        cover_bottom_mm=payload.cover_bottom_mm,
        lap_length_mm=lap,
        section=payload.section,
        notes=payload.notes,
    )
    db.add(bar)
    await db.commit()
    await db.refresh(bar)
    return _enrich(bar)


@router.put("/{bar_id}", response_model=BBSBarOut)
async def update_bar(project_id: UUID, bar_id: UUID, payload: BBSBarUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(BBSBar).where(BBSBar.id == bar_id, BBSBar.project_id == project_id))
    bar = result.scalar_one_or_none()
    if not bar:
        raise HTTPException(status_code=404, detail="Bar not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(bar, field, value)
    await db.commit()
    await db.refresh(bar)
    return _enrich(bar)


@router.delete("/{bar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bar(project_id: UUID, bar_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(BBSBar).where(BBSBar.id == bar_id, BBSBar.project_id == project_id))
    bar = result.scalar_one_or_none()
    if not bar:
        raise HTTPException(status_code=404, detail="Bar not found")
    await db.delete(bar)
    await db.commit()


@router.get("/cutting-list", response_model=list[CuttingListItem])
async def cutting_list(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(BBSBar).where(BBSBar.project_id == project_id))
    bars = result.scalars().all()

    groups: dict[tuple, dict] = {}
    for bar in bars:
        enriched = _enrich(bar)
        key = (bar.bar_diameter_mm, enriched["cutting_length_m"])
        if key not in groups:
            groups[key] = {"diameter_mm": bar.bar_diameter_mm, "cutting_length_m": enriched["cutting_length_m"], "total_qty": 0, "total_weight_kg": 0.0}
        groups[key]["total_qty"] += bar.quantity
        groups[key]["total_weight_kg"] = round(groups[key]["total_weight_kg"] + enriched["total_weight_kg"], 3)

    return list(groups.values())


@router.post("/sync-to-boq", status_code=status.HTTP_201_CREATED)
async def sync_to_boq(
    project_id: UUID,
    section: str = Query(default="SUBSTRUCTURE"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync BBS steel totals to the SuggestedQuantity table.
    Groups by diameter and creates one suggested quantity per diameter.
    This follows the Phase 2 federation workflow: Suggestion -> Review -> BOQ.
    """
    await _check_project(project_id, user, db)

    # Fetch all bars for this project and section
    result = await db.execute(
        select(BBSBar).where(
            BBSBar.project_id == project_id,
            BBSBar.section == section.upper()
        )
    )
    bars = result.scalars().all()

    if not bars:
        return {"message": f"No BBS bars found for section {section}", "count": 0}

    # Aggregate by diameter
    totals: dict[int, float] = {}
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
        totals[bar.bar_diameter_mm] = totals.get(bar.bar_diameter_mm, 0.0) + enriched["total_weight_kg"]

    # Create SuggestedQuantity entries
    created_count = 0
    for dia, weight_kg in totals.items():
        # Check if a suggestion for this diameter/section already exists to avoid duplicates
        # In a real app, we might want to update it or create a new version.
        # For now, we'll just create a new one.
        suggestion = SuggestedQuantity(
            project_id=project_id,
            discipline="STRUCTURAL",
            element_category="REINFORCEMENT",
            description=f"High yield deformed bar Ø{dia}mm (from BBS)",
            quantity_value=round(weight_kg, 3),
            quantity_unit="kg",
            section=section.upper(),
            confidence=1.0,
            notes=f"Auto-synced from BBS total for {section}",
            status="PENDING"
        )
        db.add(suggestion)
        created_count += 1

    await db.commit()

    return {
        "message": f"Synced {created_count} reinforcement totals to suggestions",
        "count": created_count,
        "section": section
    }

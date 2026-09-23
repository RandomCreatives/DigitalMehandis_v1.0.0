from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.rates.models import Rate
from app.modules.boq.models import BOQOutput
from app.modules.bbs.models import BBSBar
from app.modules.boq.schemas import BOQResult, BOQOutputOut, RateCreate, RateOut
from app.core.deps import get_current_user
from app.modules.boq.generator import BOQGenerator
from app.modules.boq.exporters import export_boq_excel, export_boq_pdf, export_bbs_excel
from app.modules.bbs.router import _enrich

router = APIRouter(prefix="/projects/{project_id}", tags=["boq"])


async def _check_project(project_id: UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Rates ─────────────────────────────────────────────────────────────────────

@router.get("/rates", response_model=list[RateOut])
async def list_rates(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(Rate).where((Rate.project_id == project_id) | (Rate.project_id.is_(None)))
    )
    return result.scalars().all()


@router.post("/rates", response_model=RateOut, status_code=201)
async def add_rate(project_id: UUID, payload: RateCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    rate = Rate(**payload.model_dump(), project_id=project_id)
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.delete("/rates/{rate_id}", status_code=204)
async def delete_rate(project_id: UUID, rate_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(Rate).where(Rate.id == rate_id, Rate.project_id == project_id))
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    await db.delete(rate)
    await db.commit()


# ── BOQ ───────────────────────────────────────────────────────────────────────

@router.post("/boq/generate", response_model=BOQResult)
async def generate_boq(
    project_id: UUID,
    section: str = Query(default="COMBINED", enum=["SUBSTRUCTURE", "SUPERSTRUCTURE", "COMBINED"]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _check_project(project_id, user, db)
    boq = await BOQGenerator(db, project_id, section).generate()

    # Cache result
    output = BOQOutput(
        project_id=project_id,
        section=section,
        total_amount=boq["total_amount"],
        currency="ETB",
    )
    db.add(output)
    await db.commit()

    return boq


@router.get("/boq", response_model=list[BOQOutputOut])
async def list_boq_outputs(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(BOQOutput).where(BOQOutput.project_id == project_id).order_by(BOQOutput.generated_at.desc()))
    return result.scalars().all()


@router.post("/boq/export-excel")
async def export_boq_to_excel(
    project_id: UUID,
    section: str = Query(default="COMBINED"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _check_project(project_id, user, db)
    boq = await BOQGenerator(db, project_id, section).generate()
    xlsx_bytes = export_boq_excel(boq, project.name)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="BOQ_{project.name}.xlsx"'},
    )


@router.post("/boq/export-pdf")
async def export_boq_to_pdf(
    project_id: UUID,
    section: str = Query(default="COMBINED"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _check_project(project_id, user, db)
    boq = await BOQGenerator(db, project_id, section).generate()
    pdf_bytes = export_boq_pdf(boq, project.name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="BOQ_{project.name}.pdf"'},
    )


@router.post("/bbs/export-excel")
async def export_bbs_to_excel(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _check_project(project_id, user, db)
    result = await db.execute(select(BBSBar).where(BBSBar.project_id == project_id))
    bars = [_enrich(b) for b in result.scalars().all()]

    # Build cutting list
    groups: dict = {}
    for bar in bars:
        key = (bar["bar_diameter_mm"], bar["cutting_length_m"])
        if key not in groups:
            groups[key] = {"diameter_mm": bar["bar_diameter_mm"], "cutting_length_m": bar["cutting_length_m"], "total_qty": 0, "total_weight_kg": 0.0}
        groups[key]["total_qty"] += bar["quantity"]
        groups[key]["total_weight_kg"] = round(groups[key]["total_weight_kg"] + bar["total_weight_kg"], 3)

    xlsx_bytes = export_bbs_excel(bars, list(groups.values()), project.name)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="BBS_{project.name}.xlsx"'},
    )

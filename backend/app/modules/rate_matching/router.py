"""
Rate Matching + Pricing Settings API

Pricing Settings:
  GET    /projects/{id}/pricing-settings           — get or create default
  PATCH  /projects/{id}/pricing-settings           — update
  GET    /projects/{id}/pricing-settings/defaults  — suggested overhead/profit

Rate Matching:
  POST   /projects/{id}/rates/auto-match           — run auto-matching
  GET    /projects/{id}/rate-matches               — list matches
  PATCH  /projects/{id}/rate-matches/{match_id}/approve  — approve
  PATCH  /projects/{id}/rate-matches/{match_id}/reject   — reject
  POST   /projects/{id}/elements/{element_id}/manual-rate — set manual rate

Enhanced BOQ:
  POST   /projects/{id}/boq/generate-v2            — generate BOQ v2
"""
import uuid
from collections import defaultdict
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.db.session import get_db
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.elements.models import ProjectElement
from app.modules.measurements.models import Measurement
from app.modules.rate_matching.models import ProjectPricingSettings, ElementRateMatch
from app.modules.cost_library.models import RateItem
from app.core.deps import get_current_user
from app.modules.rate_matching.pricing import PricingEngine, PricingMode, PricingSettings
from app.modules.rate_matching.service import RateMatchingService

router = APIRouter(tags=["rate-matching"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_project(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return project


async def _get_or_create_settings(
    project_id: uuid.UUID, db: AsyncSession
) -> ProjectPricingSettings:
    result = await db.execute(
        select(ProjectPricingSettings).where(
            ProjectPricingSettings.project_id == project_id
        )
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ProjectPricingSettings(project_id=project_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


def _build_pricing_settings(ps: ProjectPricingSettings) -> PricingSettings:
    try:
        mode = PricingMode(ps.pricing_mode)
    except ValueError:
        mode = PricingMode.ADDITIVE
    return PricingSettings(
        overhead_percent=ps.overhead_percent,
        profit_percent=ps.profit_percent,
        tax_percent=ps.tax_percent,
        mode=mode,
    )


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class PricingSettingsOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    selected_rate_source_id: uuid.UUID | None
    contractor_grade: str | None
    overhead_percent: float
    profit_percent: float
    tax_percent: float
    pricing_mode: str
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class PricingSettingsUpdate(BaseModel):
    selected_rate_source_id: uuid.UUID | None = None
    contractor_grade: str | None = None
    overhead_percent: float | None = None
    profit_percent: float | None = None
    tax_percent: float | None = None
    pricing_mode: str | None = None


class PricingDefaultsOut(BaseModel):
    contractor_grade: str | None
    suggested_overhead_percent: float
    estimated_value: float | None
    suggested_profit_percent: float
    formula_preview: str


class ElementRateMatchOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_element_id: uuid.UUID
    rate_item_id: uuid.UUID | None
    match_confidence: float
    match_reason: str | None
    status: str
    applied_direct_cost: float | None
    applied_final_rate: float | None
    override_reason: str | None
    created_by: uuid.UUID | None
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class ManualRateRequest(BaseModel):
    direct_cost: float
    rate_item_id: uuid.UUID | None = None
    override_reason: str | None = None


class ApproveMatchRequest(BaseModel):
    override_reason: str | None = None


class RejectMatchRequest(BaseModel):
    override_reason: str | None = None


class BOQLineV2(BaseModel):
    item_no: str
    section: str
    work_category: str | None
    description: str
    unit: str
    quantity: float
    direct_cost: float
    overhead_pct: float
    profit_pct: float
    final_unit_rate: float
    amount: float
    source_element_ids: list[str]
    match_status: str


class BOQSectionV2(BaseModel):
    section: str
    items: list[BOQLineV2]
    subtotal: float


class BOQV2Response(BaseModel):
    project_id: str
    pricing_mode: str
    overhead_pct: float
    profit_pct: float
    tax_pct: float
    sections: list[BOQSectionV2]
    grand_total: float
    warnings: list[str]


# ── Pricing Settings ──────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/pricing-settings",
    response_model=PricingSettingsOut,
)
async def get_pricing_settings(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    settings = await _get_or_create_settings(project_id, db)
    return settings


@router.patch(
    "/projects/{project_id}/pricing-settings",
    response_model=PricingSettingsOut,
)
async def update_pricing_settings(
    project_id: uuid.UUID,
    payload: PricingSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    settings = await _get_or_create_settings(project_id, db)

    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)
    return settings


@router.get(
    "/projects/{project_id}/pricing-settings/defaults",
    response_model=PricingDefaultsOut,
)
async def get_pricing_defaults(
    project_id: uuid.UUID,
    contractor_grade: str | None = None,
    estimated_value: float | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)

    suggested_overhead = PricingEngine.suggested_overhead(contractor_grade or "")
    suggested_profit = PricingEngine.suggested_profit(estimated_value or 0.0)

    formula_preview = (
        f"Direct Cost × (1 + {suggested_overhead}% + {suggested_profit}%) "
        f"= Final Rate (ADDITIVE mode)"
    )

    return PricingDefaultsOut(
        contractor_grade=contractor_grade,
        suggested_overhead_percent=suggested_overhead,
        estimated_value=estimated_value,
        suggested_profit_percent=suggested_profit,
        formula_preview=formula_preview,
    )


# ── Rate Matching ─────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/rates/auto-match")
async def auto_match_rates(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run auto-matching for all ACTIVE project elements.
    Uses the project's selected rate source (or all sources if none selected).
    Creates ElementRateMatch records with status=SUGGESTED.
    """
    await _check_project(project_id, user, db)
    settings = await _get_or_create_settings(project_id, db)
    pricing = _build_pricing_settings(settings)

    # Load elements
    elem_result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.project_id == project_id,
            ProjectElement.status == "ACTIVE",
        )
    )
    elements = elem_result.scalars().all()

    if not elements:
        return {"matched": 0, "total_elements": 0, "message": "No active elements found"}

    # Load rate items (filtered by selected source if set)
    rate_stmt = select(RateItem)
    if settings.selected_rate_source_id:
        rate_stmt = rate_stmt.where(
            RateItem.rate_source_id == settings.selected_rate_source_id
        )
    rate_result = await db.execute(rate_stmt)
    rate_items = rate_result.scalars().all()

    if not rate_items:
        return {
            "matched": 0,
            "total_elements": len(elements),
            "message": "No rate items found in selected source",
        }

    matched_count = 0
    for elem in elements:
        # Remove existing SUGGESTED matches for this element
        existing_stmt = select(ElementRateMatch).where(
            ElementRateMatch.project_element_id == elem.id,
            ElementRateMatch.status == "SUGGESTED",
        )
        existing_result = await db.execute(existing_stmt)
        for old_match in existing_result.scalars().all():
            await db.delete(old_match)

        # Find best match
        matches = RateMatchingService.find_best_matches(
            element_category=elem.element_type,
            element_description=getattr(elem, "material", "") or elem.element_type,
            element_unit=_infer_unit(elem.element_type),
            rate_items=rate_items,
            top_n=1,
        )

        if matches:
            best = matches[0]
            final_rate = PricingEngine.final_unit_rate(best["direct_cost"], pricing)
            match = ElementRateMatch(
                project_id=project_id,
                project_element_id=elem.id,
                rate_item_id=uuid.UUID(best["rate_item_id"]),
                match_confidence=best["confidence"],
                match_reason=best["reason"],
                status="SUGGESTED",
                applied_direct_cost=best["direct_cost"],
                applied_final_rate=final_rate,
                created_by=user.id,
            )
            db.add(match)
            matched_count += 1

    await db.commit()
    return {
        "matched": matched_count,
        "total_elements": len(elements),
        "unmatched": len(elements) - matched_count,
    }


def _infer_unit(element_type: str) -> str:
    """Infer a default unit from element type for matching purposes."""
    area_types = {"WALL", "SLAB", "FLOOR", "CEILING", "ROOF", "PLASTER", "TILE", "PAINT"}
    volume_types = {"COLUMN", "BEAM", "FOOTING", "CONCRETE", "EXCAVATION"}
    length_types = {"PIPE", "CONDUIT"}
    if element_type.upper() in area_types:
        return "m2"
    if element_type.upper() in volume_types:
        return "m3"
    if element_type.upper() in length_types:
        return "m"
    return "pcs"


@router.get(
    "/projects/{project_id}/rate-matches",
    response_model=list[ElementRateMatchOut],
)
async def list_rate_matches(
    project_id: uuid.UUID,
    match_status: str | None = Query(None, alias="status"),
    element_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    stmt = select(ElementRateMatch).where(ElementRateMatch.project_id == project_id)
    if match_status:
        stmt = stmt.where(ElementRateMatch.status == match_status.upper())
    if element_id:
        stmt = stmt.where(ElementRateMatch.project_element_id == element_id)
    stmt = stmt.order_by(ElementRateMatch.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch(
    "/projects/{project_id}/rate-matches/{match_id}/approve",
    response_model=ElementRateMatchOut,
)
async def approve_rate_match(
    project_id: uuid.UUID,
    match_id: uuid.UUID,
    payload: ApproveMatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(ElementRateMatch).where(
            ElementRateMatch.id == match_id,
            ElementRateMatch.project_id == project_id,
        )
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(404, "Rate match not found")

    match.status = "APPROVED"
    if payload.override_reason:
        match.override_reason = payload.override_reason

    await db.commit()
    await db.refresh(match)
    return match


@router.patch(
    "/projects/{project_id}/rate-matches/{match_id}/reject",
    response_model=ElementRateMatchOut,
)
async def reject_rate_match(
    project_id: uuid.UUID,
    match_id: uuid.UUID,
    payload: RejectMatchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(ElementRateMatch).where(
            ElementRateMatch.id == match_id,
            ElementRateMatch.project_id == project_id,
        )
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(404, "Rate match not found")

    match.status = "REJECTED"
    if payload.override_reason:
        match.override_reason = payload.override_reason

    await db.commit()
    await db.refresh(match)
    return match


@router.post(
    "/projects/{project_id}/elements/{element_id}/manual-rate",
    response_model=ElementRateMatchOut,
    status_code=status.HTTP_201_CREATED,
)
async def set_manual_rate(
    project_id: uuid.UUID,
    element_id: uuid.UUID,
    payload: ManualRateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a manual rate for a project element — creates a MANUAL match."""
    await _check_project(project_id, user, db)

    # Verify element belongs to project
    elem_result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.id == element_id,
            ProjectElement.project_id == project_id,
        )
    )
    if not elem_result.scalar_one_or_none():
        raise HTTPException(404, "Element not found")

    settings = await _get_or_create_settings(project_id, db)
    pricing = _build_pricing_settings(settings)
    final_rate = PricingEngine.final_unit_rate(payload.direct_cost, pricing)

    match = ElementRateMatch(
        project_id=project_id,
        project_element_id=element_id,
        rate_item_id=payload.rate_item_id,
        match_confidence=1.0,
        match_reason="Manual rate entry",
        status="MANUAL",
        applied_direct_cost=payload.direct_cost,
        applied_final_rate=final_rate,
        override_reason=payload.override_reason,
        created_by=user.id,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


# ── Enhanced BOQ Generation ───────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/boq/generate-v2",
    response_model=BOQV2Response,
)
async def generate_boq_v2(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate BOQ v2 from approved elements + approved/manual rate matches
    + project pricing settings.

    Groups by section → work_category → description.
    Returns section subtotals, grand total, and warnings for unmatched elements.
    """
    await _check_project(project_id, user, db)
    settings = await _get_or_create_settings(project_id, db)
    pricing = _build_pricing_settings(settings)

    # Load approved/manual matches with their rate items
    match_stmt = select(ElementRateMatch).where(
        ElementRateMatch.project_id == project_id,
        ElementRateMatch.status.in_(["APPROVED", "MANUAL"]),
    )
    match_result = await db.execute(match_stmt)
    matches = match_result.scalars().all()

    # Load all active elements
    elem_result = await db.execute(
        select(ProjectElement).where(
            ProjectElement.project_id == project_id,
            ProjectElement.status == "ACTIVE",
        )
    )
    all_elements = {str(e.id): e for e in elem_result.scalars().all()}

    # Build set of matched element IDs
    matched_element_ids = {str(m.project_element_id) for m in matches}
    unmatched_ids = set(all_elements.keys()) - matched_element_ids
    warnings: list[str] = []
    for eid in unmatched_ids:
        elem = all_elements[eid]
        warnings.append(
            f"Element '{elem.element_code}' ({elem.element_type}) has no approved rate match"
        )

    # Load rate items for matched matches
    rate_item_ids = [m.rate_item_id for m in matches if m.rate_item_id]
    rate_items_map: dict[str, RateItem] = {}
    if rate_item_ids:
        ri_result = await db.execute(
            select(RateItem).where(RateItem.id.in_(rate_item_ids))
        )
        rate_items_map = {str(ri.id): ri for ri in ri_result.scalars().all()}

    # Group by section → work_category
    # section → list of BOQLineV2
    sections_map: dict[str, list[BOQLineV2]] = defaultdict(list)

    item_counter: dict[str, int] = defaultdict(int)

    for match in matches:
        elem = all_elements.get(str(match.project_element_id))
        if not elem:
            continue

        rate_item = rate_items_map.get(str(match.rate_item_id)) if match.rate_item_id else None
        work_category = rate_item.work_category if rate_item else elem.element_type
        description = (
            rate_item.description
            if rate_item
            else (elem.material or elem.element_type)
        )
        unit = rate_item.unit if rate_item else _infer_unit(elem.element_type)
        direct_cost = match.applied_direct_cost or 0.0
        final_rate = match.applied_final_rate or PricingEngine.final_unit_rate(
            direct_cost, pricing
        )

        # Quantity: sum of final_value from linked measurements (default 1.0)
        qty_result = await db.execute(
            select(func.sum(Measurement.final_value)).where(
                Measurement.project_element_id == elem.id
            )
        )
        quantity = qty_result.scalar() or 1.0

        section = elem.section or "GENERAL"
        item_counter[section] += 1
        item_no = f"{section[:3]}.{item_counter[section]:03d}"

        amount = PricingEngine.amount(quantity, final_rate)

        line = BOQLineV2(
            item_no=item_no,
            section=section,
            work_category=work_category,
            description=description,
            unit=unit,
            quantity=round(quantity, 3),
            direct_cost=direct_cost,
            overhead_pct=settings.overhead_percent,
            profit_pct=settings.profit_percent,
            final_unit_rate=final_rate,
            amount=amount,
            source_element_ids=[str(elem.id)],
            match_status=match.status,
        )
        sections_map[section].append(line)

    # Build response sections
    sections_out: list[BOQSectionV2] = []
    grand_total = 0.0
    for section, lines in sorted(sections_map.items()):
        subtotal = round(sum(l.amount for l in lines), 2)
        grand_total += subtotal
        sections_out.append(
            BOQSectionV2(section=section, items=lines, subtotal=subtotal)
        )

    return BOQV2Response(
        project_id=str(project_id),
        pricing_mode=settings.pricing_mode,
        overhead_pct=settings.overhead_percent,
        profit_pct=settings.profit_percent,
        tax_pct=settings.tax_percent,
        sections=sections_out,
        grand_total=round(grand_total, 2),
        warnings=warnings,
    )

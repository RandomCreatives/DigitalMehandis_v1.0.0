"""
BOQ Items API — Phase 2 editable BOQ builder with source traceability.

POST   /projects/{id}/boq-items                    — create BOQ item
GET    /projects/{id}/boq-items                    — list BOQ items
PUT    /projects/{id}/boq-items/{id}               — update BOQ item
DELETE /projects/{id}/boq-items/{id}               — delete BOQ item
GET    /projects/{id}/boq-items/{id}/sources       — get source traceability
POST   /projects/{id}/boq-items/{id}/sources       — add source to BOQ item
POST   /projects/{id}/boq-items/from-quantities    — bulk create from approved quantities
GET    /projects/{id}/boq-items/summary            — BOQ summary with totals
"""
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.db.session import get_db
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.takeoff.models import FederatedQuantity
from app.modules.rates.models import Rate
from app.modules.boq_items.models import BOQItem, BOQItemSource, QuantitySource
from app.modules.measurements.models import Measurement
from app.modules.audit.models import AuditLog
from app.core.deps import get_current_user

router = APIRouter(tags=["boq-items"])

BOQ_SECTIONS = {
    "PRELIMINARIES", "SUBSTRUCTURE", "SUPERSTRUCTURE",
    "ELECTRICAL", "SANITARY", "EXTERNAL_WORKS",
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class BOQItemCreate(BaseModel):
    item_no: str
    section: str
    trade: str | None = None
    description: str
    unit: str
    quantity: float
    rate: float = 0.0
    waste_factor: float = 0.0
    notes: str | None = None
    sort_order: int = 0


class BOQItemUpdate(BaseModel):
    item_no: str | None = None
    section: str | None = None
    trade: str | None = None
    description: str | None = None
    unit: str | None = None
    quantity: float | None = None
    rate: float | None = None
    waste_factor: float | None = None
    notes: str | None = None
    sort_order: int | None = None
    is_locked: bool | None = None


class BOQItemOut(BaseModel):
    id: UUID
    project_id: UUID
    item_no: str
    section: str
    trade: str | None
    description: str
    unit: str
    quantity: float
    rate: float
    amount: float
    waste_factor: float
    notes: str | None
    is_locked: bool
    sort_order: int
    created_at: Any
    updated_at: Any

    model_config = {"from_attributes": True}


class BOQItemSourceCreate(BaseModel):
    suggested_quantity_id: UUID | None = None
    measurement_id: UUID | None = None
    project_element_id: UUID | None = None
    contribution_quantity: float
    unit: str
    notes: str | None = None


class BOQItemSourceOut(BaseModel):
    id: UUID
    boq_item_id: UUID
    suggested_quantity_id: UUID | None
    measurement_id: UUID | None
    project_element_id: UUID | None
    contribution_quantity: float
    unit: str
    notes: str | None
    # Enriched fields
    source_label: str | None = None
    source_drawing: str | None = None
    source_page: int | None = None

    model_config = {"from_attributes": True}


class BulkFromQuantitiesPayload(BaseModel):
    section: str = "SUBSTRUCTURE"
    auto_match_rates: bool = True


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _check_project(project_id: UUID, user: User, db: AsyncSession) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")


def _compute_amount(quantity: float, rate: float, waste_factor: float) -> float:
    qty_with_waste = quantity * (1 + waste_factor / 100)
    return round(qty_with_waste * rate, 2)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/boq-items",
    response_model=BOQItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_boq_item(
    project_id: UUID,
    payload: BOQItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)

    amount = _compute_amount(payload.quantity, payload.rate, payload.waste_factor)

    item = BOQItem(
        project_id=project_id,
        item_no=payload.item_no,
        section=payload.section.upper(),
        trade=payload.trade,
        description=payload.description,
        unit=payload.unit,
        quantity=payload.quantity,
        rate=payload.rate,
        amount=amount,
        waste_factor=payload.waste_factor,
        notes=payload.notes,
        sort_order=payload.sort_order,
        created_by=user.id,
    )
    db.add(item)

    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="BOQ_ITEM_CREATED",
        entity_type="BOQItem",
        description=f"BOQ item {payload.item_no}: {payload.description} — {payload.quantity} {payload.unit} @ {payload.rate} ETB",
    ))

    await db.commit()
    await db.refresh(item)
    return item


@router.get(
    "/projects/{project_id}/boq-items",
    response_model=list[BOQItemOut],
)
async def list_boq_items(
    project_id: UUID,
    section: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    stmt = select(BOQItem).where(BOQItem.project_id == project_id)
    if section:
        stmt = stmt.where(BOQItem.section == section.upper())
    result = await db.execute(stmt.order_by(BOQItem.section, BOQItem.sort_order, BOQItem.item_no))
    return result.scalars().all()


@router.get(
    "/projects/{project_id}/boq-items/summary",
)
async def boq_summary(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """BOQ summary with totals by section."""
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(BOQItem).where(BOQItem.project_id == project_id)
    )
    items = result.scalars().all()

    by_section: dict = {}
    grand_total = 0.0

    for item in items:
        sec = item.section
        if sec not in by_section:
            by_section[sec] = {"section": sec, "items": 0, "total": 0.0}
        by_section[sec]["items"] += 1
        by_section[sec]["total"] += item.amount
        grand_total += item.amount

    return {
        "project_id": str(project_id),
        "sections": list(by_section.values()),
        "grand_total": round(grand_total, 2),
        "currency": "ETB",
        "total_items": len(items),
    }


@router.put(
    "/projects/{project_id}/boq-items/{item_id}",
    response_model=BOQItemOut,
)
async def update_boq_item(
    project_id: UUID,
    item_id: UUID,
    payload: BOQItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(BOQItem).where(BOQItem.id == item_id, BOQItem.project_id == project_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "BOQ item not found")
    if item.is_locked:
        raise HTTPException(400, "BOQ item is locked and cannot be edited")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)

    # Recompute amount
    item.amount = _compute_amount(item.quantity, item.rate, item.waste_factor)

    await db.commit()
    await db.refresh(item)
    return item


@router.delete(
    "/projects/{project_id}/boq-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_boq_item(
    project_id: UUID,
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(BOQItem).where(BOQItem.id == item_id, BOQItem.project_id == project_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "BOQ item not found")
    if item.is_locked:
        raise HTTPException(400, "Cannot delete a locked BOQ item")
    await db.delete(item)
    await db.commit()


@router.get(
    "/projects/{project_id}/boq-items/{item_id}/sources",
)
async def get_boq_item_sources(
    project_id: UUID,
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get full source traceability for a BOQ item.
    Shows which measurements, drawings, and elements contributed.
    """
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(BOQItem).where(BOQItem.id == item_id, BOQItem.project_id == project_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "BOQ item not found")

    sources_result = await db.execute(
        select(BOQItemSource).where(BOQItemSource.boq_item_id == item_id)
    )
    sources = sources_result.scalars().all()

    enriched = []
    for src in sources:
        entry = {
            "id": str(src.id),
            "contribution_quantity": src.contribution_quantity,
            "unit": src.unit,
            "notes": src.notes,
            "suggested_quantity_id": str(src.suggested_quantity_id) if src.suggested_quantity_id else None,
            "measurement_id": str(src.measurement_id) if src.measurement_id else None,
            "project_element_id": str(src.project_element_id) if src.project_element_id else None,
            "source_label": None,
            "source_drawing": None,
            "source_page": None,
        }

        # Enrich with measurement details
        if src.measurement_id:
            m_result = await db.execute(
                select(Measurement).where(Measurement.id == src.measurement_id)
            )
            m = m_result.scalar_one_or_none()
            if m:
                entry["source_label"] = m.label
                entry["source_drawing"] = str(m.drawing_id)
                entry["source_page"] = m.page_number

        enriched.append(entry)

    return {
        "boq_item": {
            "id": str(item.id),
            "item_no": item.item_no,
            "description": item.description,
            "quantity": item.quantity,
            "unit": item.unit,
            "rate": item.rate,
            "amount": item.amount,
        },
        "sources": enriched,
        "source_count": len(enriched),
    }


@router.post(
    "/projects/{project_id}/boq-items/{item_id}/sources",
    status_code=status.HTTP_201_CREATED,
)
async def add_source_to_boq_item(
    project_id: UUID,
    item_id: UUID,
    payload: BOQItemSourceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link a measurement or approved quantity as a source for this BOQ item."""
    await _check_project(project_id, user, db)
    result = await db.execute(
        select(BOQItem).where(BOQItem.id == item_id, BOQItem.project_id == project_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "BOQ item not found")

    src = BOQItemSource(
        boq_item_id=item_id,
        suggested_quantity_id=payload.suggested_quantity_id,
        measurement_id=payload.measurement_id,
        project_element_id=payload.project_element_id,
        contribution_quantity=payload.contribution_quantity,
        unit=payload.unit,
        notes=payload.notes,
    )
    db.add(src)
    await db.commit()
    await db.refresh(src)

    return {"id": str(src.id), "message": "Source linked to BOQ item"}


@router.post(
    "/projects/{project_id}/boq-items/from-quantities",
    status_code=status.HTTP_201_CREATED,
)
async def create_boq_from_quantities(
    project_id: UUID,
    payload: BulkFromQuantitiesPayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk-create BOQ items from all approved (federated) quantities.
    Optionally auto-matches rates from the rate database.
    """
    await _check_project(project_id, user, db)

    # Get approved quantities for this section
    fq_result = await db.execute(
        select(FederatedQuantity).where(
            FederatedQuantity.project_id == project_id,
            FederatedQuantity.section == payload.section.upper(),
        )
    )
    quantities = fq_result.scalars().all()

    if not quantities:
        return {"message": "No approved quantities found for this section", "created": 0}

    # Get rates for matching
    rates_result = await db.execute(
        select(Rate).where(
            (Rate.project_id == project_id) | (Rate.project_id.is_(None))
        )
    )
    rates = rates_result.scalars().all()

    def find_rate(description: str, unit: str) -> float:
        """Simple substring match for rate lookup."""
        desc_lower = description.lower()
        for rate in rates:
            if rate.unit == unit and any(
                word in desc_lower for word in rate.description.lower().split()
                if len(word) > 3
            ):
                return float(rate.rate_per_unit)
        return 0.0

    created = []
    for i, fq in enumerate(quantities):
        rate_value = find_rate(fq.element_description, fq.quantity_unit) if payload.auto_match_rates else 0.0
        amount = _compute_amount(float(fq.quantity_value), rate_value, 0.0)

        item = BOQItem(
            project_id=project_id,
            item_no=f"{i+1}",
            section=payload.section.upper(),
            trade=fq.element_category,
            description=fq.element_description,
            unit=fq.quantity_unit,
            quantity=float(fq.quantity_value),
            rate=rate_value,
            amount=amount,
            created_by=user.id,
        )
        db.add(item)
        await db.flush()

        # Create source link
        src = BOQItemSource(
            boq_item_id=item.id,
            suggested_quantity_id=fq.suggested_quantity_id,
            contribution_quantity=float(fq.quantity_value),
            unit=fq.quantity_unit,
        )
        db.add(src)
        created.append(item.id)

    db.add(AuditLog(
        project_id=project_id,
        user_id=user.id,
        action="BOQ_GENERATED",
        entity_type="BOQItem",
        description=f"BOQ generated from {len(created)} approved quantities for {payload.section}",
    ))

    await db.commit()
    return {
        "message": f"Created {len(created)} BOQ items from approved quantities",
        "created": len(created),
        "section": payload.section,
    }

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.modules.cost_library.models import RateSource, RateItem
from app.modules.elements.models import ProjectElement
from app.modules.cost_library.schemas import RateSourceOut, RateItemOut, AddToProjectRequest
from app.modules.elements.schemas import ProjectElementOut
from app.core.deps import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/cost-library", tags=["cost-library"])

@router.get("/sources", response_model=list[RateSourceOut])
async def list_rate_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RateSource).order_by(RateSource.created_at.desc()))
    sources = result.scalars().all()

    out = []
    for s in sources:
        count_res = await db.execute(select(func.count(RateItem.id)).where(RateItem.rate_source_id == s.id))
        item_count = count_res.scalar() or 0
        s_out = RateSourceOut.model_validate(s)
        s_out.item_count = item_count
        out.append(s_out)
    return out

@router.get("/sources/{source_id}/tree", response_model=list[RateItemOut])
async def get_rate_tree(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns the hierarchical tree of rates for a source."""
    # We fetch only roots (no parent_id) and use selectinload for children
    stmt = (
        select(RateItem)
        .where(RateItem.rate_source_id == source_id, RateItem.parent_id.is_(None))
        .options(selectinload(RateItem.children))
        .order_by(RateItem.item_no)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/search", response_model=list[RateItemOut])
async def search_rates(
    q: str = Query(..., min_length=2),
    source_id: uuid.UUID | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Flat search across all items."""
    stmt = select(RateItem).where(
        or_(
            RateItem.description.ilike(f"%{q}%"),
            RateItem.item_no.ilike(f"%{q}%")
        )
    )
    if source_id:
        stmt = stmt.where(RateItem.rate_source_id == source_id)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/add-to-project", response_model=ProjectElementOut, status_code=status.HTTP_201_CREATED)
async def add_to_project(
    payload: AddToProjectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a ProjectElement (takeoff template) from a RateItem.
    """
    rate_item = await db.get(RateItem, payload.rate_item_id)
    if not rate_item:
        raise HTTPException(404, "Rate item not found")

    element = ProjectElement(
        project_id=payload.project_id,
        element_code=rate_item.item_no or "TBD",
        element_type="TAKEOFF_TEMPLATE",
        discipline="GENERAL", # In real app, we might infer from MoWUD hierarchy
        section=payload.section,
        floor_level=payload.floor_level,
        material=rate_item.description,
        source_type="COST_LIBRARY",
        confidence=1.0,
        specification={
            "rate_item_id": str(rate_item.id),
            "original_rate": rate_item.direct_cost,
            "unit": rate_item.unit
        },
        created_by=user.id
    )

    db.add(element)
    await db.commit()
    await db.refresh(element)
    return element

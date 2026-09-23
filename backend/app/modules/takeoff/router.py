from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.takeoff.models import TakeoffItem
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.takeoff.schemas import TakeoffItemCreate, TakeoffItemUpdate, TakeoffItemOut
from app.core.deps import get_current_user

router = APIRouter(prefix="/projects/{project_id}/takeoff", tags=["takeoff"])


async def _check_project(project_id: UUID, user: User, db: AsyncSession):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("", response_model=list[TakeoffItemOut])
async def list_items(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(TakeoffItem).where(TakeoffItem.project_id == project_id))
    return result.scalars().all()


@router.post("", response_model=TakeoffItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(project_id: UUID, payload: TakeoffItemCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    item = TakeoffItem(**payload.model_dump(), project_id=project_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=TakeoffItemOut)
async def update_item(project_id: UUID, item_id: UUID, payload: TakeoffItemUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(TakeoffItem).where(TakeoffItem.id == item_id, TakeoffItem.project_id == project_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(project_id: UUID, item_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _check_project(project_id, user, db)
    result = await db.execute(select(TakeoffItem).where(TakeoffItem.id == item_id, TakeoffItem.project_id == project_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()

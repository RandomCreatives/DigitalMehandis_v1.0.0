from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.projects.schemas import ProjectCreate, ProjectUpdate, ProjectOut
from app.core.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_project_or_404(project_id: UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.user_id == user.id).order_by(Project.updated_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = Project(**payload.model_dump(), user_id=user.id, rate_database_version="1.0")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _get_project_or_404(project_id, user, db)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: UUID, payload: ProjectUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await _get_project_or_404(project_id, user, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await _get_project_or_404(project_id, user, db)
    await db.delete(project)
    await db.commit()

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.cad.models import LayerMappingTemplate, LayerMapping, BlockMapping
from app.core.deps import get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])

@router.post("")
async def create_template(
    name: str,
    project_id: UUID,
    description: str = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch all mappings for this project
    layers = (await db.execute(select(LayerMapping).where(LayerMapping.project_id == project_id))).scalars().all()
    blocks = (await db.execute(select(BlockMapping).where(BlockMapping.project_id == project_id))).scalars().all()

    mappings = {
        "layers": [{"name": l.layer_name, "key": l.task_key} for l in layers],
        "blocks": [{"name": b.block_name, "key": b.task_key} for b in blocks]
    }

    tpl = LayerMappingTemplate(
        user_id=user.id,
        name=name,
        description=description,
        mappings_json=mappings
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl

@router.get("")
async def list_templates(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LayerMappingTemplate).where(
        (LayerMappingTemplate.user_id == user.id) | (LayerMappingTemplate.is_public == True)
    ))
    return result.scalars().all()

@router.post("/{template_id}/apply")
async def apply_template(
    template_id: UUID,
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    tpl = await db.get(LayerMappingTemplate, template_id)
    if not tpl: raise HTTPException(404, "Template not found")

    mappings = tpl.mappings_json

    # Apply layers
    for lm in mappings.get("layers", []):
        existing = (await db.execute(select(LayerMapping).where(LayerMapping.project_id == project_id, LayerMapping.layer_name == lm["name"]))).scalar_one_or_none()
        if not existing:
            db.add(LayerMapping(project_id=project_id, layer_name=lm["name"], discipline="AR", task_key=lm["key"], mapped_by="template"))

    # Apply blocks
    for bm in mappings.get("blocks", []):
        existing = (await db.execute(select(BlockMapping).where(BlockMapping.project_id == project_id, BlockMapping.block_name == bm["name"]))).scalar_one_or_none()
        if not existing:
            db.add(BlockMapping(project_id=project_id, block_name=bm["name"], discipline="AR", task_key=bm["key"], mapped_by="template"))

    await db.commit()
    return {"message": "Template applied successfully."}

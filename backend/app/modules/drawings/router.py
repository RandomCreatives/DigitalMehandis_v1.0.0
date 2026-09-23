"""
Drawings API — updated for Phase 3 CAD automation.
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db, AsyncSessionLocal
from app.modules.drawings.models import Drawing
from app.modules.projects.models import Project
from app.modules.auth.models import User
from app.modules.boq_items.models import BOQItem
from app.modules.cad.models import DXFLayer, DXFBlock, DXFAnalysisJob, LayerMapping, BlockMapping, QuantitySuggestion, DXFEntity, LayerMappingTemplate, DrawingRevision
from app.modules.drawings.schemas import DrawingOut, DXFLayerOut, DXFBlockOut, DXFLayerUpdate, DXFBlockUpdate, ConversionRequest, QuantitySuggestionOut, QuantitySuggestionReview
from app.core.deps import get_current_user
from app.core.files import save_upload, delete_file
from app.modules.cad.extraction import ExtractionService
from app.modules.cad.conversion import ConversionService
from app.modules.cad.bbs_extraction import BBSExtractionService
from app.modules.cad.revision import RevisionService

router = APIRouter(tags=["drawings"])

async def _get_project(project_id: UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

async def _get_drawing(drawing_id: UUID, project_id: UUID, db: AsyncSession) -> Drawing:
    result = await db.execute(select(Drawing).where(Drawing.id == drawing_id, Drawing.project_id == project_id))
    drawing = result.scalar_one_or_none()
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")
    return drawing

async def process_drawing_task(project_id: UUID, drawing_id: UUID, file_path: str, discipline: str, is_dxf: bool):
    async with AsyncSessionLocal() as db:
        try:
            await ExtractionService.extract_from_drawing(
                project_id=project_id,
                drawing_id=drawing_id,
                file_path=file_path,
                discipline=discipline,
                is_dxf=is_dxf,
                db=db
            )
        except Exception as e:
            print(f"Background task failed: {e}")

@router.post("/projects/{project_id}/drawings/upload", status_code=status.HTTP_201_CREATED)
async def upload_drawing(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Query(default="ARCHITECTURAL"),
    discipline: str = Query(default="ARCHITECTURAL"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, user, db)
    filename = (file.filename or "").lower()
    is_dxf = filename.endswith(".dxf")

    meta = await save_upload(file, str(project_id))
    drawing = Drawing(
        project_id=project_id,
        filename=meta["original_filename"],
        file_path=meta["file_path"],
        file_size_mb=meta["file_size_mb"],
        category=category.upper(),
        page_count=meta.get("page_count", 1),
    )
    db.add(drawing)
    await db.commit()
    await db.refresh(drawing)

    background_tasks.add_task(
        process_drawing_task,
        project_id,
        drawing.id,
        meta["file_path"],
        discipline,
        is_dxf
    )

    return {
        "drawing": DrawingOut.model_validate(drawing),
        "is_dxf": is_dxf,
        "message": "Drawing uploaded and analysis started in background (Beta).",
    }

@router.get("/projects/{project_id}/drawings", response_model=list[DrawingOut])
async def list_drawings(project_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(Drawing).where(Drawing.project_id == project_id).order_by(Drawing.uploaded_at.desc()))
    return result.scalars().all()

@router.get("/projects/{project_id}/drawings/{drawing_id}/layers", response_model=list[DXFLayerOut])
async def get_drawing_layers(project_id: UUID, drawing_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(DXFLayer).where(DXFLayer.drawing_id == drawing_id).order_by(DXFLayer.layer_name))
    return result.scalars().all()

@router.patch("/projects/{project_id}/drawings/{drawing_id}/layers/{layer_id}", response_model=DXFLayerOut)
async def update_layer_mapping(project_id: UUID, drawing_id: UUID, layer_id: UUID, payload: DXFLayerUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(DXFLayer).where(DXFLayer.id == layer_id, DXFLayer.drawing_id == drawing_id))
    layer = result.scalar_one_or_none()
    if not layer: raise HTTPException(404, "Layer not found")

    if payload.user_override is not None:
        layer.user_override = payload.user_override
        map_res = await db.execute(select(LayerMapping).where(LayerMapping.project_id == project_id, LayerMapping.layer_name == layer.layer_name))
        m = map_res.scalar_one_or_none()
        if not m:
            m = LayerMapping(project_id=project_id, layer_name=layer.layer_name, discipline="AR", task_key=payload.user_override, mapped_by="user")
            db.add(m)
        else:
            m.task_key = payload.user_override
            m.mapped_by = "user"

    if payload.is_ignored is not None: layer.is_ignored = payload.is_ignored

    await db.commit()
    await db.refresh(layer)
    return layer

@router.get("/projects/{project_id}/drawings/{drawing_id}/blocks", response_model=list[DXFBlockOut])
async def get_drawing_blocks(project_id: UUID, drawing_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(DXFBlock).where(DXFBlock.drawing_id == drawing_id).order_by(DXFBlock.block_name))
    return result.scalars().all()

@router.patch("/projects/{project_id}/drawings/{drawing_id}/blocks/{block_id}", response_model=DXFBlockOut)
async def update_block_mapping(project_id: UUID, drawing_id: UUID, block_id: UUID, payload: DXFBlockUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(DXFBlock).where(DXFBlock.id == block_id, DXFBlock.drawing_id == drawing_id))
    block = result.scalar_one_or_none()
    if not block: raise HTTPException(404, "Block not found")

    if payload.user_override is not None:
        block.user_override = payload.user_override
        map_res = await db.execute(select(BlockMapping).where(BlockMapping.project_id == project_id, BlockMapping.block_name == block.block_name))
        m = map_res.scalar_one_or_none()
        if not m:
            m = BlockMapping(project_id=project_id, block_name=block.block_name, discipline="AR", task_key=payload.user_override, mapped_by="user")
            db.add(m)
        else:
            m.task_key = payload.user_override
            m.mapped_by = "user"

    await db.commit()
    await db.refresh(block)
    return block

@router.post("/projects/{project_id}/drawings/{drawing_id}/process")
async def process_drawing_to_suggestions(
    project_id: UUID,
    drawing_id: UUID,
    payload: ConversionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _get_project(project_id, user, db)
    multipliers = payload.model_dump()
    count = await ConversionService.process_drawing_to_suggestions(project_id, drawing_id, db, multipliers)
    return {"message": f"Successfully generated {count} suggestions.", "count": count}

@router.post("/projects/{project_id}/drawings/{drawing_id}/extract-bbs")
async def extract_bbs(
    project_id: UUID,
    drawing_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _get_project(project_id, user, db)
    count = await BBSExtractionService.extract_bbs_from_drawing(drawing_id, project_id, db)
    return {"message": f"Successfully extracted {count} BBS entries.", "count": count}

@router.get("/projects/{project_id}/suggestions", response_model=list[QuantitySuggestionOut])
async def list_suggestions(
    project_id: UUID,
    status: str = Query(default="PENDING"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _get_project(project_id, user, db)
    result = await db.execute(select(QuantitySuggestion).where(
        QuantitySuggestion.project_id == project_id,
        QuantitySuggestion.status == status.upper()
    ))
    return result.scalars().all()

@router.post("/projects/{project_id}/suggestions/{suggestion_id}/review")
async def review_suggestion(
    project_id: UUID,
    suggestion_id: UUID,
    payload: QuantitySuggestionReview,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _get_project(project_id, user, db)
    result = await db.execute(select(QuantitySuggestion).where(QuantitySuggestion.id == suggestion_id))
    sq = result.scalar_one_or_none()
    if not sq: raise HTTPException(404, "Suggestion not found")

    sq.status = payload.status.upper()
    sq.reviewed_at = datetime.now(timezone.utc)
    sq.reviewed_by = user.id
    if payload.final_quantity is not None: sq.final_quantity = payload.final_quantity
    if payload.notes: sq.notes = payload.notes

    if sq.status in ("APPROVED", "EDITED"):
        # Create actual BOQ item
        final_qty = sq.final_quantity if sq.final_quantity is not None else sq.final_value
        boq_item = BOQItem(
            project_id=project_id,
            item_no="AUTO", # Will be assigned by BOQ sequencer
            section=sq.discipline,
            description=f"{sq.task_label} (Auto from {sq.source_layer or sq.source_block})",
            unit=sq.unit,
            quantity=final_qty,
            rate=0.0, # Will be filled if rate_id exists
            amount=0.0
        )
        db.add(boq_item)

    await db.commit()
    return {"message": f"Suggestion {sq.status.lower()} successfully."}

@router.get("/projects/{project_id}/suggestions/{suggestion_id}/source")
async def get_suggestion_source(
    project_id: UUID,
    suggestion_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _get_project(project_id, user, db)
    result = await db.execute(select(QuantitySuggestion).where(QuantitySuggestion.id == suggestion_id))
    sq = result.scalar_one_or_none()
    if not sq: raise HTTPException(404, "Suggestion not found")

    handles = sq.entity_ids.get("handles", []) if sq.entity_ids else []
    entities_res = await db.execute(select(DXFEntity).where(
        DXFEntity.drawing_id == sq.drawing_id,
        DXFEntity.handle.in_(handles)
    ))
    return entities_res.scalars().all()

@router.get("/projects/{project_id}/drawings/{drawing_id}/revisions")
async def list_revisions(
    project_id: UUID,
    drawing_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await _get_project(project_id, user, db)
    result = await db.execute(select(DrawingRevision).where(DrawingRevision.drawing_id == drawing_id).order_by(DrawingRevision.revision_number.desc()))
    return result.scalars().all()

@router.get("/projects/{project_id}/drawings/{drawing_id}/canvas-data")
async def get_canvas_data(project_id: UUID, drawing_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    drawing = await _get_drawing(drawing_id, project_id, db)

    if drawing.filename.lower().endswith(".dxf"):
        extractor = ExtractionService.get_extractor(drawing.file_path)
        return extractor.to_canvas_json()
    else:
        return {"type": "PDF"}

@router.get("/projects/{project_id}/drawings/{drawing_id}/analysis-status")
async def get_analysis_status(project_id: UUID, drawing_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_project(project_id, user, db)
    result = await db.execute(select(DXFAnalysisJob).where(DXFAnalysisJob.drawing_id == drawing_id).order_by(DXFAnalysisJob.created_at.desc()))
    job = result.scalar_one_or_none()
    if not job: return {"status": "NOT_STARTED"}
    return {
        "status": job.status,
        "entities_found": job.entities_found,
        "layers_found": job.layers_found,
        "suggestions_generated": job.suggestions_generated
    }


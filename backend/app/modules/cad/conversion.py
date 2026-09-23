import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.cad.models import DXFEntity, DXFLayer, DXFBlock, QuantitySuggestion
from app.modules.drawings.models import Drawing
from app.modules.rate_matching.service import RateMatchingService

logger = logging.getLogger(__name__)

class ConversionService:
    @staticmethod
    async def process_drawing_to_suggestions(
        project_id: UUID,
        drawing_id: UUID,
        db: AsyncSession,
        multipliers: Optional[Dict[str, float]] = None
    ) -> int:
        """
        Converts classified DXF entities into Quantity Suggestions.
        """
        multipliers = multipliers or {}
        # Default multipliers
        wall_height = multipliers.get("wall_height", 3.0)
        slab_thickness = multipliers.get("slab_thickness", 0.15)
        floor_count = multipliers.get("floor_count", 1.0)
        beam_width = multipliers.get("beam_width", 0.25)
        beam_depth = multipliers.get("beam_depth", 0.5)

        # 1. Get drawing info (units/scale)
        drawing_res = await db.execute(select(Drawing).where(Drawing.id == drawing_id))
        drawing = drawing_res.scalar_one()

        # 2. Get all classified layers
        layer_res = await db.execute(select(DXFLayer).where(DXFLayer.drawing_id == drawing_id, DXFLayer.is_ignored == False))
        layers = layer_res.scalars().all()

        suggestions_count = 0

        for layer in layers:
            classification = layer.user_override or layer.classified_as
            if not classification or classification == "UNKNOWN":
                continue

            # Process entities for this layer
            entity_res = await db.execute(select(DXFEntity).where(DXFEntity.drawing_id == drawing_id, DXFEntity.layer_name == layer.layer_name))
            entities = entity_res.scalars().all()
            if not entities: continue

            suggestion = None

            if classification == "WALL":
                total_length = sum(e.length or 0 for e in entities)
                suggestion = QuantitySuggestion(
                    project_id=project_id, drawing_id=drawing_id, discipline="AR",
                    task_key="MASONRY", task_label="HCB Wall (Auto)",
                    source_layer=layer.layer_name, entity_count=len(entities),
                    entity_ids={"handles": [e.handle for e in entities]},
                    raw_value=total_length,
                    final_value=total_length * wall_height,
                    unit="m²", multiplier=wall_height,
                    formula_applied=f"length ({total_length:.2f}m) x height ({wall_height}m)",
                    confidence=layer.confidence, status="PENDING"
                )

            elif classification == "COLUMN":
                total_area = sum(e.area or 0 for e in entities)
                suggestion = QuantitySuggestion(
                    project_id=project_id, drawing_id=drawing_id, discipline="ST",
                    task_key="CONCRETE", task_label="Concrete Column (Auto)",
                    source_layer=layer.layer_name, entity_count=len(entities),
                    entity_ids={"handles": [e.handle for e in entities]},
                    raw_value=total_area,
                    final_value=total_area * wall_height * floor_count,
                    unit="m³", multiplier=wall_height * floor_count,
                    formula_applied=f"area ({total_area:.2f}m²) x height ({wall_height}m) x floors ({floor_count})",
                    confidence=layer.confidence, status="PENDING"
                )

            elif classification == "SLAB":
                total_area = sum(e.area or 0 for e in entities)
                suggestion = QuantitySuggestion(
                    project_id=project_id, drawing_id=drawing_id, discipline="ST",
                    task_key="CONCRETE", task_label="Concrete Slab (Auto)",
                    source_layer=layer.layer_name, entity_count=len(entities),
                    entity_ids={"handles": [e.handle for e in entities]},
                    raw_value=total_area,
                    final_value=total_area * slab_thickness,
                    unit="m³", multiplier=slab_thickness,
                    formula_applied=f"area ({total_area:.2f}m²) x thickness ({slab_thickness}m)",
                    confidence=layer.confidence, status="PENDING"
                )

            elif classification == "BEAM":
                total_length = sum(e.length or 0 for e in entities)
                suggestion = QuantitySuggestion(
                    project_id=project_id, drawing_id=drawing_id, discipline="ST",
                    task_key="CONCRETE", task_label="Concrete Beam (Auto)",
                    source_layer=layer.layer_name, entity_count=len(entities),
                    entity_ids={"handles": [e.handle for e in entities]},
                    raw_value=total_length,
                    final_value=total_length * beam_width * beam_depth,
                    unit="m³", multiplier=beam_width * beam_depth,
                    formula_applied=f"length ({total_length:.2f}m) x width ({beam_width}m) x depth ({beam_depth}m)",
                    confidence=layer.confidence, status="PENDING"
                )

            if suggestion:
                # Try rate matching
                match = await RateMatchingService.match_rate(suggestion.task_label, suggestion.discipline)
                if match:
                    suggestion.suggested_rate_id = match[0].id
                    suggestion.suggested_rate_confidence = 0.8

                db.add(suggestion)
                suggestions_count += 1

        # 3. Process Blocks
        block_res = await db.execute(select(DXFBlock).where(DXFBlock.drawing_id == drawing_id))
        blocks = block_res.scalars().all()
        for block in blocks:
            classification = block.user_override or block.classified_as
            if not classification or classification == "UNKNOWN":
                continue

            entities_res = await db.execute(select(DXFEntity).where(DXFEntity.drawing_id == drawing_id, DXFEntity.block_name == block.block_name))
            entities = entities_res.scalars().all()
            if not entities: continue

            suggestion = QuantitySuggestion(
                project_id=project_id, drawing_id=drawing_id, discipline="AR",
                task_key="WOOD_METAL_WORK", task_label=f"{classification.title()} (Auto)",
                source_block=block.block_name, entity_count=len(entities),
                entity_ids={"handles": [e.handle for e in entities]},
                raw_value=float(len(entities)),
                final_value=float(len(entities)),
                unit="Nr", multiplier=1.0,
                formula_applied="count",
                confidence=block.confidence, status="PENDING"
            )

            # Rate matching...
            db.add(suggestion)
            suggestions_count += 1

        await db.commit()
        return suggestions_count

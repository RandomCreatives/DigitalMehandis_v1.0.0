import logging
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from rapidfuzz import fuzz, process

from app.modules.cad.models import DXFLayer, DXFBlock, LayerMapping, BlockMapping, DXFEntity
from app.modules.cad.symbol_classifier import SymbolClassifier

logger = logging.getLogger(__name__)

class ClassificationService:
    @staticmethod
    async def classify_layers(drawing_id: UUID, project_id: UUID, db: AsyncSession):
        """
        Classifies all layers for a given drawing using multiple strategies.
        """
        result = await db.execute(select(DXFLayer).where(DXFLayer.drawing_id == drawing_id))
        layers = result.scalars().all()

        # Pre-fetch user mappings for this project
        map_result = await db.execute(select(LayerMapping).where(LayerMapping.project_id == project_id))
        user_mappings = {m.layer_name: m for m in map_result.scalars().all()}

        for layer in layers:
            # Strategy 1: User Mapping History
            if layer.layer_name in user_mappings:
                m = user_mappings[layer.layer_name]
                layer.classified_as = m.task_key
                layer.strategy_used = "USER_MAPPED"
                layer.confidence = 1.0
                continue

            # Strategy 2, 3, 5: Name based
            classification, strategy, confidence = await ClassificationService._classify_layer_name(
                layer.layer_name, project_id, db
            )

            # Strategy 4: Geometry Inference (if name-based is weak)
            if classification == "UNKNOWN" or confidence < 0.6:
                geom_class, geom_conf = await ClassificationService._infer_from_geometry(drawing_id, layer.layer_name, db)
                if geom_class != "UNKNOWN":
                    classification = geom_class
                    strategy = "GEOMETRY_INFERENCE"
                    confidence = geom_conf

            layer.classified_as = classification
            layer.strategy_used = strategy
            layer.confidence = confidence

        await db.commit()

    @staticmethod
    async def _classify_layer_name(name: str, project_id: UUID, db: AsyncSession) -> Tuple[str, str, float]:
        name_lower = name.lower()

        # Strategy 2: Keyword match
        keywords = {
            "WALL": ["wall", "hcb", "masonry", "partition"],
            "COLUMN": ["col", "column", "pillar"],
            "BEAM": ["beam", "bm"],
            "SLAB": ["slab", "floor", "floor_area"],
            "DOOR": ["door", "dr"],
            "WINDOW": ["window", "wd", "win"],
            "LIGHT": ["light", "fixture", "lamp", "led"],
            "SOCKET": ["socket", "outlet", "plug"],
            "PIPE": ["pipe", "drain", "sewer", "plumbing"],
            "FOOTING": ["footing", "fnd", "foundation"]
        }

        for category, kws in keywords.items():
            for kw in kws:
                if kw in name_lower:
                    return category, "KEYWORD_MATCH", 0.85

        # Strategy 3: Prefix Match
        if name_lower.startswith(("a-", "ar-")): return "ARCHITECTURAL_GENERIC", "PREFIX_MATCH", 0.55
        if name_lower.startswith(("s-", "st-")): return "STRUCTURAL_GENERIC", "PREFIX_MATCH", 0.55
        if name_lower.startswith(("e-", "el-")): return "ELECTRICAL_GENERIC", "PREFIX_MATCH", 0.55
        if name_lower.startswith(("p-", "sn-")): return "SANITARY_GENERIC", "PREFIX_MATCH", 0.55

        # Strategy 5: Fuzzy String Match
        all_categories = list(keywords.keys())
        best_match = process.extractOne(name_lower, all_categories, scorer=fuzz.partial_ratio)
        if best_match and best_match[1] > 80:
            return best_match[0], "FUZZY_MATCH", best_match[1] / 100.0

        return "UNKNOWN", "NONE", 0.0

    @staticmethod
    async def _infer_from_geometry(drawing_id: UUID, layer_name: str, db: AsyncSession) -> Tuple[str, float]:
        # Simple heuristic based on entity types and properties
        stmt = select(DXFEntity.entity_type, func.count(DXFEntity.id)).where(
            DXFEntity.drawing_id == drawing_id,
            DXFEntity.layer_name == layer_name
        ).group_by(DXFEntity.entity_type)

        counts = dict((await db.execute(stmt)).all())
        total = sum(counts.values())
        if total == 0: return "UNKNOWN", 0.0

        # If mostly INSERTs -> Likely fixtures
        if counts.get("INSERT", 0) / total > 0.8:
            return "FIXTURE_GENERIC", 0.6

        # If mostly closed polylines of small area -> Likely columns
        # (This would need actual area checks, skipping for MVP)

        return "UNKNOWN", 0.0

    @staticmethod
    async def classify_blocks(drawing_id: UUID, project_id: UUID, db: AsyncSession):
        """
        Classifies all blocks for a given drawing using the Ethiopian Symbol Classifier.
        """
        result = await db.execute(select(DXFBlock).where(DXFBlock.drawing_id == drawing_id))
        blocks = result.scalars().all()

        # Pre-fetch user mappings
        map_result = await db.execute(select(BlockMapping).where(BlockMapping.project_id == project_id))
        user_mappings = {m.block_name: m for m in map_result.scalars().all()}

        for block in blocks:
            if block.block_name in user_mappings:
                m = user_mappings[block.block_name]
                block.classified_as = m.task_key
                block.confidence = 1.0
                continue

            category = SymbolClassifier.classify_block(block.block_name)
            if category != "UNKNOWN":
                block.classified_as = category
                block.confidence = 0.95
            else:
                block.classified_as = "UNKNOWN"
                block.confidence = 0.0

        await db.commit()

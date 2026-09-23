import logging
import asyncio
from typing import Any, Dict, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.takeoff.schemas import CanonicalQuantity
from app.modules.cad.pdf_processor import PDFProcessor
from app.modules.cad.dxf_parser import DXFEntityExtractor
from app.modules.cad.federation_engine import FederationEngine, Discipline
from app.modules.cad.classification import ClassificationService
from app.modules.cad.models import DXFEntity, DXFLayer, DXFBlock, DXFAnalysisJob, QuantitySuggestion

logger = logging.getLogger(__name__)

class ExtractionService:
    _extractors: Dict[str, DXFEntityExtractor] = {}

    @staticmethod
    def get_extractor(file_path: str) -> DXFEntityExtractor:
        if file_path not in ExtractionService._extractors:
            ExtractionService._extractors[file_path] = DXFEntityExtractor(file_path)
        return ExtractionService._extractors[file_path]

    @staticmethod
    async def extract_from_drawing(
        project_id: UUID,
        drawing_id: UUID,
        file_path: str,
        discipline: str,
        is_dxf: bool,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Orchestrates extraction from PDF or DXF and generates quantity suggestions.
        """
        disc_enum = Discipline(discipline.upper())

        job = DXFAnalysisJob(drawing_id=drawing_id, status="PROCESSING", started_at=datetime.now(timezone.utc))
        db.add(job)
        await db.flush()

        try:
            units_info = None
            if is_dxf:
                extractor = ExtractionService.get_extractor(file_path)
                units_info = extractor.get_units()

                # Persist Layers
                layers_summary = extractor.get_layers_summary()
                for lname, counts in layers_summary.items():
                    db.add(DXFLayer(
                        drawing_id=drawing_id,
                        layer_name=lname,
                        entity_count=sum(counts.values()),
                        confidence=0.0,
                        is_ignored=False
                    ))

                # Persist Blocks
                blocks_summary = extractor.get_blocks_summary()
                for bname, count in blocks_summary.items():
                    db.add(DXFBlock(
                        drawing_id=drawing_id,
                        block_name=bname,
                        count=count,
                        confidence=0.0
                    ))

                # Persist Entities
                entities = extractor.extract_all_for_persistence()
                for e in entities:
                    db.add(DXFEntity(
                        drawing_id=drawing_id,
                        layer_name=e.layer,
                        entity_type=e.dxftype,
                        geometry_json=e.geometry,
                        length=e.length,
                        area=e.area,
                        text_content=e.text,
                        block_name=e.block_name,
                        position_x=e.position[0] if e.position else None,
                        position_y=e.position[1] if e.position else None,
                        handle=e.handle
                    ))

                await db.flush() # Ensure layers/blocks are in DB for classifier

                # Trigger Classification
                await ClassificationService.classify_layers(drawing_id, project_id, db)
                await ClassificationService.classify_blocks(drawing_id, project_id, db)

                canvas_json = extractor.to_canvas_json()
                extracted_data = {"layers": layers_summary}

                job.entities_found = len(entities)
                job.layers_found = len(layers_summary)

            else:
                processor = PDFProcessor()
                layout = processor.extract_text_and_layout(file_path)
                canvas_json = processor.pdf_to_canvas_json(file_path, page_number=1)
                extracted_data = ExtractionService._layout_to_extracted_data(layout)

            # Generate Federation Suggestions
            engine = FederationEngine(str(project_id))
            engine.add_from_drawing(str(drawing_id), disc_enum, extracted_data)
            suggestions = engine.get_suggestions()

            # Persist Suggestions
            for s in suggestions:
                db.add(QuantitySuggestion(
                    project_id=project_id,
                    drawing_id=drawing_id,
                    discipline=s.discipline,
                    task_key="PENDING",
                    task_label=s.element_category,
                    raw_value=s.value,
                    final_value=s.value,
                    unit=s.unit,
                    multiplier=1.0,
                    source_layer=s.source_layer,
                    confidence=s.confidence,
                    status="PENDING",
                ))

            job.status = "COMPLETED"
            job.completed_at = datetime.now(timezone.utc)
            job.suggestions_generated = len(suggestions)

            await db.commit()

            return {
                "canvas_json": canvas_json,
                "suggestions_count": len(suggestions),
                "units_info": units_info
            }

        except Exception as e:
            logger.exception(f"Error during extraction for drawing {drawing_id}")
            job.status = "FAILED"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise

    @staticmethod
    def _layout_to_extracted_data(layout: dict) -> dict:
        layers: dict = {}
        for page in layout.get("pages", []):
            layer_name = f"PDF_PAGE_{page['page_number']}"
            layers[layer_name] = {
                "lines": [],
                "polylines": [],
                "texts": [{"text": w["text"], "position": (w["x0"], w["top"]), "layer": layer_name} for w in page.get("words", [])],
            }
        return {"layers": layers}

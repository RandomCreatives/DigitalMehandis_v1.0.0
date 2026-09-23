"""
Federation Engine — extracts quantity SUGGESTIONS from parsed drawing data.
Enhanced for Ethiopian context (MoUDC codes) and multi-discipline support.
"""
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from app.modules.cad.symbol_classifier import SymbolClassifier
from app.modules.cad.geometry_calculator import GeometryCalculator

logger = logging.getLogger(__name__)

class MoUDCCode:
    """Ethiopian Ministry of Urban Development and Construction (MoUDC) Classification Codes."""
    EXCAVATION = "1100"
    CONCRETE_SUB = "2100"
    CONCRETE_SUP = "2200"
    MASONRY = "3100"
    REINFORCEMENT_8 = "2411"
    REINFORCEMENT_10_PLUS = "2412"
    FORM_WORK = "2500"
    FINISHING_PLASTER = "4100"
    FINISHING_PAINT = "4500"
    WOOD_WORK = "5100"
    METAL_WORK = "5500"
    ELECTRICAL_FIX = "6100"
    SANITARY_FIX = "7100"

class Discipline(str, Enum):
    ARCHITECTURAL = "ARCHITECTURAL"
    STRUCTURAL = "STRUCTURAL"
    ELECTRICAL = "ELECTRICAL"
    SANITARY = "SANITARY"

class Section(str, Enum):
    SUBSTRUCTURE = "SUBSTRUCTURE"
    SUPERSTRUCTURE = "SUPERSTRUCTURE"

@dataclass
class QuantitySuggestion:
    discipline: str
    element_category: str
    description: str
    value: float
    unit: str
    section: str
    source_drawing_id: str
    source_layer: str = ""
    confidence: float = 0.8
    notes: str = ""
    moudc_code: Optional[str] = None

class FederationEngine:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.suggestions: List[QuantitySuggestion] = []

    def add_from_drawing(self, drawing_id: str, discipline: Discipline, extracted_data: Dict[str, Any]) -> None:
        logger.info(f"Federation: processing {discipline} drawing {drawing_id}")
        match discipline:
            case Discipline.ARCHITECTURAL:
                self._process_architectural(drawing_id, extracted_data)
            case Discipline.STRUCTURAL:
                self._process_structural(drawing_id, extracted_data)
            case Discipline.ELECTRICAL:
                self._process_electrical(drawing_id, extracted_data)
            case Discipline.SANITARY:
                self._process_sanitary(drawing_id, extracted_data)

    def _process_architectural(self, drawing_id: str, data: Dict[str, Any]) -> None:
        for layer_name, ld in data.get("layers", {}).items():
            layer_lower = layer_name.lower()
            if "wall" in layer_lower:
                for poly in ld.get("polylines", []):
                    self._add(QuantitySuggestion(
                        discipline=Discipline.ARCHITECTURAL,
                        element_category="WALL",
                        description=f"Wall (MoUDC {MoUDCCode.MASONRY})",
                        value=round(poly["length"], 3),
                        unit="m",
                        section=Section.SUPERSTRUCTURE,
                        source_drawing_id=drawing_id,
                        source_layer=layer_name,
                        moudc_code=MoUDCCode.MASONRY
                    ))
            if any(k in layer_lower for k in ("room", "floor")):
                 for poly in ld.get("polylines", []):
                    if poly.get("is_closed"):
                        self._add(QuantitySuggestion(
                            discipline=Discipline.ARCHITECTURAL,
                            element_category="FLOOR_AREA",
                            description=f"Floor area (layer: {layer_name})",
                            value=round(poly["area"], 3),
                            unit="m²",
                            section=Section.SUPERSTRUCTURE,
                            source_drawing_id=drawing_id,
                            source_layer=layer_name,
                            confidence=0.7,
                        ))

        block_counts = self._collect_block_counts(data)
        classified = SymbolClassifier.get_quantities_by_discipline(block_counts)
        for category, count in classified.get("ARCHITECTURAL", {}).items():
            if category in ("DOOR", "WINDOW"):
                self._add(QuantitySuggestion(
                    discipline=Discipline.ARCHITECTURAL,
                    element_category=category,
                    description=f"{category.title()} count (MoUDC {MoUDCCode.WOOD_WORK}/{MoUDCCode.METAL_WORK})",
                    value=float(count),
                    unit="Nr",
                    section=Section.SUPERSTRUCTURE,
                    source_drawing_id=drawing_id,
                    confidence=0.85,
                    moudc_code=MoUDCCode.WOOD_WORK if category=="DOOR" else MoUDCCode.METAL_WORK
                ))

    def _process_structural(self, drawing_id: str, data: Dict[str, Any]) -> None:
        for layer_name, ld in data.get("layers", {}).items():
            layer_lower = layer_name.lower()
            if any(k in layer_lower for k in ("footing", "fnd")):
                for poly in ld.get("polylines", []):
                    if poly.get("is_closed"):
                        self._add(QuantitySuggestion(
                            discipline=Discipline.STRUCTURAL,
                            element_category="FOOTING",
                            description=f"Concrete Footing (MoUDC {MoUDCCode.CONCRETE_SUB})",
                            value=round(poly["area"], 3),
                            unit="m²",
                            section=Section.SUBSTRUCTURE,
                            source_drawing_id=drawing_id,
                            moudc_code=MoUDCCode.CONCRETE_SUB
                        ))

    def _process_electrical(self, drawing_id: str, data: Dict[str, Any]) -> None:
        block_counts = self._collect_block_counts(data)
        classified = SymbolClassifier.get_quantities_by_discipline(block_counts)
        for category, count in classified.get("ELECTRICAL", {}).items():
            self._add(QuantitySuggestion(
                discipline=Discipline.ELECTRICAL,
                element_category=category,
                description=f"{category.replace('_', ' ').title()} (MoUDC {MoUDCCode.ELECTRICAL_FIX})",
                value=float(count),
                unit="Nr",
                section=Section.SUPERSTRUCTURE,
                source_drawing_id=drawing_id,
                moudc_code=MoUDCCode.ELECTRICAL_FIX
            ))

    def _process_sanitary(self, drawing_id: str, data: Dict[str, Any]) -> None:
        block_counts = self._collect_block_counts(data)
        classified = SymbolClassifier.get_quantities_by_discipline(block_counts)
        for category, count in classified.get("SANITARY", {}).items():
            self._add(QuantitySuggestion(
                discipline=Discipline.SANITARY,
                element_category=category,
                description=f"{category.replace('_', ' ').title()} (MoUDC {MoUDCCode.SANITARY_FIX})",
                value=float(count),
                unit="Nr",
                section=Section.SUPERSTRUCTURE,
                source_drawing_id=drawing_id,
                moudc_code=MoUDCCode.SANITARY_FIX
            ))

    def _add(self, suggestion: QuantitySuggestion) -> None:
        if suggestion.value > 0:
            self.suggestions.append(suggestion)

    def get_suggestions(self) -> List[QuantitySuggestion]:
        return self.suggestions

    @staticmethod
    def _collect_block_counts(data: Dict[str, Any]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for ld in data.get("layers", {}).values():
            for block in ld.get("blocks", []):
                name = block["block_name"]
                counts[name] = counts.get(name, 0) + 1
        return counts

import math
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple, Union
import ezdxf
from ezdxf.document import Drawing as DXFDrawing
from app.modules.takeoff.schemas import CanonicalQuantity
from app.modules.cad.geometry_calculator import GeometryCalculator

logger = logging.getLogger(__name__)

@dataclass
class DXFEntityData:
    handle: str
    layer: str
    dxftype: str
    geometry: Dict[str, Any]
    length: Optional[float] = None
    area: Optional[float] = None
    text: Optional[str] = None
    block_name: Optional[str] = None
    position: Optional[Tuple[float, float]] = None

class DXFEntityExtractor:
    def __init__(self, file_path: str):
        try:
            self.doc: DXFDrawing = ezdxf.readfile(file_path)
            self.msp = self.doc.modelspace()
        except Exception as e:
            logger.error(f"Failed to read DXF file {file_path}: {e}")
            raise

    def get_units(self) -> Dict[str, Any]:
        """
        Detects units from DXF header.
        Returns a dict with 'code', 'label', and 'needs_calibration'.
        """
        unit_map = {
            1: "Inches",
            2: "Feet",
            4: "Millimeters",
            5: "Centimeters",
            6: "Meters",
        }
        try:
            code = self.doc.header.get("$INSUNITS", 0)
            return {
                "code": code,
                "label": unit_map.get(code, "Unknown"),
                "needs_calibration": code == 0
            }
        except Exception:
            return {"code": 0, "label": "Unknown", "needs_calibration": True}

    def extract_all_for_persistence(self) -> List[DXFEntityData]:
        entities = []
        for entity in self.msp:
            etype = entity.dxftype()
            layer = entity.dxf.layer
            handle = entity.dxf.handle

            data = DXFEntityData(
                handle=handle,
                layer=layer,
                dxftype=etype,
                geometry={}
            )

            if etype == "LINE":
                start = (entity.dxf.start.x, entity.dxf.start.y)
                end = (entity.dxf.end.x, entity.dxf.end.y)
                data.length = GeometryCalculator.point_distance(start, end)
                data.geometry = {"start": start, "end": end}

            elif etype in ("LWPOLYLINE", "POLYLINE"):
                points = [(p[0], p[1]) for p in entity.get_points(format="xy")]
                data.length = GeometryCalculator.polyline_length(points)
                data.geometry = {"points": points, "is_closed": bool(entity.closed)}
                if entity.closed:
                    # Simple shoelace for area if closed
                    data.area = self._calculate_area(points)

            elif etype == "CIRCLE":
                data.geometry = {"center": (entity.dxf.center.x, entity.dxf.center.y), "radius": entity.dxf.radius}
                data.area = math.pi * (entity.dxf.radius ** 2)

            elif etype in ("TEXT", "MTEXT"):
                data.text = entity.dxf.text if etype == "TEXT" else entity.text
                data.position = (entity.dxf.insert.x, entity.dxf.insert.y)
                data.geometry = {"position": data.position, "height": getattr(entity.dxf, "height", 2.5)}

            elif etype == "INSERT":
                data.block_name = entity.dxf.name
                data.position = (entity.dxf.insert.x, entity.dxf.insert.y)
                data.geometry = {"position": data.position, "rotation": getattr(entity.dxf, "rotation", 0.0)}

            elif etype == "HATCH":
                try:
                    data.area = entity.area()
                except:
                    pass

            entities.append(data)
        return entities

    def get_layers_summary(self) -> Dict[str, Dict[str, int]]:
        summary = {}
        for entity in self.msp:
            layer = entity.dxf.layer
            etype = entity.dxftype()
            if layer not in summary:
                summary[layer] = {}
            summary[layer][etype] = summary[layer].get(etype, 0) + 1
        return summary

    def get_blocks_summary(self) -> Dict[str, int]:
        summary = {}
        for entity in self.msp:
            if entity.dxftype() == "INSERT":
                name = entity.dxf.name
                summary[name] = summary.get(name, 0) + 1
        return summary

    def _calculate_area(self, points: List[Tuple[float, float]]) -> float:
        """Shoelace formula for area."""
        n = len(points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0

    def to_canvas_json(self) -> Dict[str, Any]:
        # Keep existing lightweight canvas export for UI rendering
        data = {"layers": {}, "viewbox": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}}
        all_x, all_y = [], []
        for entity in self.msp:
            layer = entity.dxf.layer
            etype = entity.dxftype()
            if layer not in data["layers"]:
                data["layers"][layer] = {"lines": [], "circles": [], "texts": []}

            if etype == "LINE":
                data["layers"][layer]["lines"].append({
                    "x1": entity.dxf.start.x, "y1": entity.dxf.start.y,
                    "x2": entity.dxf.end.x, "y2": entity.dxf.end.y
                })
                all_x.extend([entity.dxf.start.x, entity.dxf.end.x])
                all_y.extend([entity.dxf.start.y, entity.dxf.end.y])
            # Add more for basic visualization if needed...

        if all_x and all_y:
            data["viewbox"] = {"min_x": min(all_x), "min_y": min(all_y), "max_x": max(all_x), "max_y": max(all_y)}
        return data


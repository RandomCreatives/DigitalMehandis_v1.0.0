import re
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.cad.models import DXFEntity
from app.modules.bbs.models import BBSBar

logger = logging.getLogger(__name__)

class BBSExtractionService:
    # Patterns: 4Y16, Y8@150, 2T12, 10-diameter32
    CALLOUT_PATTERNS = [
        r'(\d+)[YyTt](\d+)',        # Count + Diameter (4Y16)
        r'[YyTt](\d+)@(\d+)',       # Diameter + Spacing (Y8@150)
        r'Ø(\d+)', r'(\d+)φ(\d+)',                  # Diameter only (Ø16)
        r'(\d+)%%c(\d+)',           # Count + Diameter with AutoCAD code (4%%c16)
    ]

    @staticmethod
    async def extract_bbs_from_drawing(drawing_id: UUID, project_id: UUID, db: AsyncSession) -> int:
        """
        Scans TEXT/MTEXT for rebar callouts and associates them with nearby structural members.
        """
        # 1. Get all text entities
        stmt = select(DXFEntity).where(
            DXFEntity.drawing_id == drawing_id,
            DXFEntity.entity_type.in_(["TEXT", "MTEXT"])
        )
        texts = (await db.execute(stmt)).scalars().all()

        # 2. Get all potential structural members (closed polylines on COLUMN/BEAM layers)
        # For simplicity in MVP, we just find all closed polylines
        stmt_members = select(DXFEntity).where(
            DXFEntity.drawing_id == drawing_id,
            DXFEntity.entity_type.in_(["LWPOLYLINE", "POLYLINE"])
        )
        members = (await db.execute(stmt_members)).scalars().all()

        bars_found = 0

        for t in texts:
            content = (t.text_content or "").strip()
            match_data = BBSExtractionService._parse_callout(content)
            if not match_data: continue

            # 3. Association by proximity (strict 500mm limit)
            # DXF positions are typically in mm or meters.
            # Assuming mm for this logic, 500 units.
            closest_member = BBSExtractionService._find_nearest(t, members, limit=500.0)

            member_name = closest_member.layer_name if closest_member else "Unknown Member"

            bar = BBSBar(
                project_id=project_id,
                bar_mark="AUTO",
                member_name=f"{member_name} (Auto)",
                bar_diameter_mm=match_data["diameter"],
                bar_shape="00", # Default straight
                quantity=match_data["count"] or 1,
                clear_length_m=3.0, # Placeholder, needs manual input
                section="SUPERSTRUCTURE",
                notes=f"Auto-extracted from text: '{content}'"
            )
            db.add(bar)
            bars_found += 1

        await db.commit()
        return bars_found

    @staticmethod
    def _parse_callout(text: str) -> Optional[Dict[str, Any]]:
        # 4Y16
        m = re.search(r'(\d+)[YyTt](\d+)', text)
        if m:
            return {"count": int(m.group(1)), "diameter": int(m.group(2))}

        # Y8@150
        m = re.search(r'[YyTt](\d+)@(\d+)', text)
        if m:
            # Need to estimate count from spacing and member length... complex.
            # Just return diameter for now.
            return {"count": None, "diameter": int(m.group(1)), "spacing": int(m.group(2))}

        return None

    @staticmethod
    def _find_nearest(text_entity: DXFEntity, members: List[DXFEntity], limit: float) -> Optional[DXFEntity]:
        if not text_entity.position_x or not text_entity.position_y: return None

        tx, ty = text_entity.position_x, text_entity.position_y
        best_m = None
        min_dist = limit

        for m in members:
            # Simple check against member insertion/position or center
            mx = m.position_x
            my = m.position_y

            # If it's a polyline, use first vertex as proxy for now
            if not mx and m.geometry_json and "points" in m.geometry_json:
                pts = m.geometry_json["points"]
                if pts: mx, my = pts[0][0], pts[0][1]

            if mx is None or my is None: continue

            dist = math.sqrt((tx - mx)**2 + (ty - my)**2)
            if dist < min_dist:
                min_dist = dist
                best_m = m

        return best_m

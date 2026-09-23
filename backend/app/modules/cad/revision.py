import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.cad.models import DXFEntity, DrawingRevision
from app.modules.drawings.models import Drawing

logger = logging.getLogger(__name__)

class RevisionService:
    @staticmethod
    async def compare_revisions(drawing_id: UUID, new_file_path: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Compares new DXF version with current entities in DB using geometric identity.
        """
        # 1. Get existing entities
        stmt = select(DXFEntity).where(DXFEntity.drawing_id == drawing_id)
        old_entities = (await db.execute(stmt)).scalars().all()

        # Create a lookup map by geometry hash or handle
        # For simplicity, we use handle if available, else a simple geometry string
        old_map = {e.handle: e for e in old_entities if e.handle}

        # 2. Parse new file
        from app.modules.cad.dxf_parser import DXFEntityExtractor
        extractor = DXFEntityExtractor(new_file_path)
        new_entities = extractor.extract_all_for_persistence()

        added, deleted, changed = [], [], []
        new_handles = set()

        for ne in new_entities:
            if ne.handle in old_map:
                oe = old_map[ne.handle]
                # Compare geometry
                if ne.geometry != oe.geometry_json:
                    changed.append({"handle": ne.handle, "type": ne.dxftype, "old": oe.geometry_json, "new": ne.geometry})
                new_handles.add(ne.handle)
            else:
                added.append({"handle": ne.handle, "type": ne.dxftype})

        for handle, oe in old_map.items():
            if handle not in new_handles:
                deleted.append({"handle": handle, "type": oe.entity_type})

        summary = {
            "added_count": len(added),
            "deleted_count": len(deleted),
            "changed_count": len(changed),
            "added": added,
            "deleted": deleted,
            "changed": changed
        }

        return summary

    @staticmethod
    async def create_revision(drawing_id: UUID, file_path: str, db: AsyncSession) -> DrawingRevision:
        # Get latest rev number
        stmt = select(DrawingRevision).where(DrawingRevision.drawing_id == drawing_id).order_by(DrawingRevision.revision_number.desc())
        latest = (await db.execute(stmt)).scalar_one_or_none()
        next_rev = (latest.revision_number + 1) if latest else 1

        summary = await RevisionService.compare_revisions(drawing_id, file_path, db)

        rev = DrawingRevision(
            drawing_id=drawing_id,
            revision_number=next_rev,
            file_path=file_path,
            diff_summary_json=summary
        )
        db.add(rev)
        await db.commit()
        return rev

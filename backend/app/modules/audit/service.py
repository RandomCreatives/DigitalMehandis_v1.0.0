"""
Audit helper — convenience function for logging QS actions.

Usage:
    from app.modules.audit.service import log_action

    await log_action(
        db=db,
        project_id=project_id,
        user_id=user.id,
        action="MEASUREMENT_CREATED",
        entity_type="Measurement",
        entity_id=str(measurement.id),
        new_value={"label": measurement.label, "value": measurement.final_value},
    )
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


async def log_action(
    db: AsyncSession,
    project_id: uuid.UUID | str | None,
    user_id: uuid.UUID | str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    description: str | None = None,
    ip_address: str | None = None,
    *,
    auto_flush: bool = False,
) -> AuditLog:
    """
    Create an AuditLog entry and add it to the session.

    The caller is responsible for committing the session.
    Set auto_flush=True to flush immediately (useful when you need the ID
    before the outer commit).

    Parameters
    ----------
    db          : Active async SQLAlchemy session.
    project_id  : UUID of the project (or None for system-level events).
    user_id     : UUID of the acting user (or None for automated actions).
    action      : Action constant, e.g. "MEASUREMENT_CREATED".
    entity_type : Model name, e.g. "Measurement", "BOQItem".
    entity_id   : String UUID of the affected entity.
    old_value   : JSON-serialisable dict of the previous state (for updates).
    new_value   : JSON-serialisable dict of the new state.
    description : Human-readable summary (auto-generated if omitted).
    ip_address  : Client IP address (optional, from Request.client.host).
    auto_flush  : If True, flush the session after adding the log entry.
    """
    # Normalise UUIDs to uuid.UUID objects (the column type expects them)
    def _to_uuid(v: uuid.UUID | str | None) -> uuid.UUID | None:
        if v is None:
            return None
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))

    entry = AuditLog(
        project_id=_to_uuid(project_id),
        user_id=_to_uuid(user_id),
        action=action.upper(),
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        old_value=old_value,
        new_value=new_value,
        description=description or _default_description(action, entity_type, entity_id),
        ip_address=ip_address,
    )
    db.add(entry)

    if auto_flush:
        await db.flush()

    return entry


def _default_description(
    action: str,
    entity_type: str | None,
    entity_id: str | None,
) -> str:
    """Generate a minimal human-readable description when none is provided."""
    parts = [action.replace("_", " ").title()]
    if entity_type:
        parts.append(f"on {entity_type}")
    if entity_id:
        parts.append(f"({entity_id[:8]}…)")
    return " ".join(parts)

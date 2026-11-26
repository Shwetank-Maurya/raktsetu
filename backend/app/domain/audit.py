from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.security import Principal


async def audit(
    session: AsyncSession,
    actor: Principal | None,
    action: str,
    entity: str,
    entity_id: str | int,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    session.add(AuditLog(
        actor_id=actor.uid if actor else "system",
        actor_role=actor.role if actor else "system",
        action=action, entity=entity, entity_id=str(entity_id), before=before, after=after,
    ))

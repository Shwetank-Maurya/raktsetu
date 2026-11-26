"""Row-level scoping from auth claims (edge case #42). Every read/write goes through here."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Facility, Region
from app.domain.errors import Forbidden
from app.security import Principal


async def region_subtree(session: AsyncSession, region_id: int) -> set[int]:
    regions = (await session.execute(select(Region.id, Region.parent_id))).all()
    out, frontier = {region_id}, [region_id]
    while frontier:
        cur = frontier.pop()
        for rid, parent in regions:
            if parent == cur and rid not in out:
                out.add(rid)
                frontier.append(rid)
    return out


async def allowed_facilities(session: AsyncSession, p: Principal) -> set[int] | None:
    """None means unrestricted (admin). Empty set means nothing visible."""
    if p.role == "admin":
        return None
    if p.role == "regional_coordinator":
        if p.region_id is None:
            return set()
        regions = await region_subtree(session, p.region_id)
        rows = await session.execute(select(Facility.id).where(Facility.region_id.in_(regions)))
        return set(rows.scalars().all())
    return {p.facility_id} if p.facility_id else set()


async def assert_facility(session: AsyncSession, p: Principal, facility_id: int) -> None:
    allowed = await allowed_facilities(session, p)
    if allowed is not None and facility_id not in allowed:
        raise Forbidden("facility outside your scope")


def require_role(p: Principal, *roles: str) -> None:
    if p.role not in roles and p.role != "admin":
        raise Forbidden(f"requires role: {', '.join(roles)}")

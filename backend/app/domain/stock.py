"""Derived stock views. Usable stock excludes reserved/quarantined/in-transit units and units whose
remaining life is below the component minimum (edge case #9)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BloodUnit, Facility
from app.domain.compat import RuleBook
from app.domain.ledger import now_utc

SeriesKey = tuple[int, str, str]  # facility_id, abo_rh, component


def _usable_clause(book: RuleBook, now: datetime):
    return or_(*[
        and_(BloodUnit.component == c, BloodUnit.expires_at > now + timedelta(hours=s.min_usable_hours))
        for c, s in book.shelf.items()
    ])


async def usable_counts(session: AsyncSession, book: RuleBook, facility_ids: set[int] | None = None) -> dict[SeriesKey, int]:
    now = now_utc()
    q = (select(BloodUnit.facility_id, BloodUnit.abo_rh, BloodUnit.component, func.count())
         .where(BloodUnit.status == "available", _usable_clause(book, now))
         .group_by(BloodUnit.facility_id, BloodUnit.abo_rh, BloodUnit.component))
    if facility_ids is not None:
        q = q.where(BloodUnit.facility_id.in_(facility_ids))
    return {(f, g, c): n for f, g, c, n in (await session.execute(q)).all()}


async def status_counts(session: AsyncSession, facility_ids: set[int] | None = None) -> dict[SeriesKey, dict[str, int]]:
    q = (select(BloodUnit.facility_id, BloodUnit.abo_rh, BloodUnit.component, BloodUnit.status, func.count())
         .where(BloodUnit.status.in_(("available", "reserved", "quarantined", "in_transit")))
         .group_by(BloodUnit.facility_id, BloodUnit.abo_rh, BloodUnit.component, BloodUnit.status))
    if facility_ids is not None:
        q = q.where(BloodUnit.facility_id.in_(facility_ids))
    out: dict[SeriesKey, dict[str, int]] = defaultdict(dict)
    for f, g, c, s, n in (await session.execute(q)).all():
        out[(f, g, c)][s] = n
    return out


async def expiry_profiles(session: AsyncSession, book: RuleBook, facility_ids: set[int] | None = None) -> dict[SeriesKey, list[float]]:
    """Remaining usable hours of each usable unit, sorted ascending (FEFO order), per series.
    Usable hours = hours until the unit drops below its component's minimum usable life."""
    now = now_utc()
    q = (select(BloodUnit.facility_id, BloodUnit.abo_rh, BloodUnit.component, BloodUnit.expires_at)
         .where(BloodUnit.status == "available", _usable_clause(book, now)))
    if facility_ids is not None:
        q = q.where(BloodUnit.facility_id.in_(facility_ids))
    out: dict[SeriesKey, list[float]] = defaultdict(list)
    for f, g, c, exp in (await session.execute(q)).all():
        out[(f, g, c)].append((exp - now).total_seconds() / 3600 - book.shelf[c].min_usable_hours)
    for v in out.values():
        v.sort()
    return out


async def incoming_units(session: AsyncSession) -> dict[SeriesKey, list[tuple[float, float]]]:
    """In-transit units per destination: (arrival hour, remaining usable hours at arrival)."""
    from app.db.models import TransferRequest

    now = now_utc()
    rows = (await session.execute(
        select(TransferRequest).where(TransferRequest.status == "dispatched")
    )).scalars().all()
    out: dict[SeriesKey, list[tuple[float, float]]] = defaultdict(list)
    for t in rows:
        start = t.dispatched_at or now
        arrival_h = max(0.0, (start - now).total_seconds() / 3600 + t.eta_minutes / 60)
        for _ in range(t.quantity):
            out[(t.to_facility_id, t.abo_rh, t.component)].append((arrival_h, t.min_life_on_arrival_h))
    return out


def freshness_hours(f: Facility, now: datetime | None = None) -> float | None:
    if f.last_reported_at is None:
        return None
    return ((now or now_utc()) - f.last_reported_at).total_seconds() / 3600

"""Compatibility and shelf-life lookups, loaded from the config tables with code defaults."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompatRule, ShelfLifeRule
from app.domain.rules import ABO_RH, DEFAULT_SHELF_LIFE, ShelfLife, default_compat


class RuleBook:
    """In-memory snapshot of the rule tables, passed into pure functions (optimizer, risk)."""

    def __init__(self, compat: dict[str, dict[str, tuple[str, ...]]], shelf: dict[str, ShelfLife]):
        self.compat = compat
        self.shelf = shelf

    @classmethod
    def default(cls) -> RuleBook:
        return cls(default_compat(), dict(DEFAULT_SHELF_LIFE))

    def can_give(self, component: str, donor: str, recipient: str) -> bool:
        return recipient in self.compat.get(component, {}).get(donor, ())

    def donors_for(self, component: str, recipient: str) -> list[str]:
        """Compatible donor groups for a recipient, identical group first, O- last (conserve it)."""
        out = [d for d in ABO_RH if self.can_give(component, d, recipient)]
        out.sort(key=lambda d: (d != recipient, d == "O-"))
        return out


async def load_rulebook(session: AsyncSession) -> RuleBook:
    book = RuleBook.default()
    rows = (await session.execute(select(CompatRule))).scalars().all()
    if rows:
        compat: dict[str, dict[str, list[str]]] = {}
        for r in rows:
            compat.setdefault(r.component, {}).setdefault(r.donor_abo_rh, []).append(r.recipient_abo_rh)
        book.compat = {c: {d: tuple(v) for d, v in m.items()} for c, m in compat.items()}
    for r in (await session.execute(select(ShelfLifeRule))).scalars().all():
        book.shelf[r.component] = ShelfLife(
            r.component, r.shelf_life_hours, r.min_usable_hours, r.min_life_on_arrival_hours,
            r.max_transit_hours, r.storage, r.units_per_day_floor,
        )
    return book


async def seed_rules(session: AsyncSession) -> None:
    """Idempotently write default rules to the config tables."""
    existing = (await session.execute(select(CompatRule).limit(1))).first()
    if not existing:
        for comp, table in default_compat().items():
            for donor, recips in table.items():
                for r in recips:
                    session.add(CompatRule(component=comp, donor_abo_rh=donor, recipient_abo_rh=r))
    for comp, s in DEFAULT_SHELF_LIFE.items():
        if await session.get(ShelfLifeRule, comp) is None:
            session.add(ShelfLifeRule(
                component=comp, shelf_life_hours=s.shelf_life_hours, min_usable_hours=s.min_usable_hours,
                min_life_on_arrival_hours=s.min_life_on_arrival_hours, max_transit_hours=s.max_transit_hours,
                storage=s.storage, units_per_day_floor=s.units_per_day_floor,
            ))
    await session.flush()

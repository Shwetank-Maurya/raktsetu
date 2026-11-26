"""Demo-only world ticker: advances the synthetic network by N hours through the real ledger
(issues from ground-truth demand, donor-camp receipts at blood banks, routine standing-order
replenishment) so a deployed demo does not drain to zero over days. Never used with real data."""

from __future__ import annotations

import uuid
from datetime import timedelta

import numpy as np
from sqlalchemy import select

from app.db.models import Facility
from app.db.session import get_sessionmaker
from app.domain.compat import load_rulebook
from app.domain.errors import DomainError
from app.domain.ledger import now_utc, record_event
from app.domain.rules import ABO_RH, COMPONENTS
from app.domain.stock import usable_counts
from app.ml.calendar import static_festivals
from app.schemas import InventoryEventIn
from app.security import Principal
from app.services.forecasting import today_ist
from app.sim.generator import SILENT, demand_rate, incidents_by_day
from app.sim.generator import facilities as specs

SIM_ACTOR = Principal(uid="world-sim", role="admin", name="Synthetic world", auth="system")
# Keep the demo story intact: these series are never auto-replenished.
PROTECTED = {("LH-03", "O-", "RBC"), ("TC-01", "O-", "RBC"), ("SH-02", "B-", "PLT"), ("MC-01", "O-", "RBC")}


async def tick(hours: float = 1.0, seed: int | None = None) -> dict:
    rng = np.random.default_rng(seed)
    sm = get_sessionmaker()
    today = today_ist()
    fests, inc = static_festivals(), incidents_by_day(today)
    silent_now = {c for c, ago, n in SILENT if ago - n < 0 <= ago}  # facilities currently silent stay silent
    stats = {"issued": 0, "received": 0, "replenished": 0}
    async with sm() as session:
        book = await load_rulebook(session)
        facs = {f.code: f for f in (await session.execute(select(Facility).where(Facility.active.is_(True)))).scalars()}
        usable = await usable_counts(session, book)
        tag = uuid.uuid4().hex[:8]
        for s in specs():
            f = facs.get(s.code)
            if f is None or s.code in silent_now or s.code == "SH-04":
                continue
            for g in ABO_RH:
                for c in COMPONENTS:
                    lam, _ = demand_rate(s, g, c, today, fests, inc)
                    n = int(rng.poisson(lam * hours / 24))
                    have = usable.get((f.id, g, c), 0)
                    if n and have:
                        ev = InventoryEventIn(type="issue", facility_id=f.id, abo_rh=g, component=c,
                                              quantity=min(n, have), emergency=bool(rng.random() < 0.3))
                        try:
                            await record_event(session, SIM_ACTOR, ev, f"sim:{tag}:{f.id}:{g}:{c}", source="api")
                            stats["issued"] += ev.quantity
                        except DomainError:
                            pass
                    # routine standing order: keep non-protected hospital series near 3 days of cover
                    if s.type == "hospital" and (s.code, g, c) not in PROTECTED and lam > 0.05:
                        target = int(np.ceil(lam * (2 if c == "PLT" else 3)))
                        if have - n < target * 0.5:
                            q = max(1, target - max(0, have - n))
                            await _receive(session, f.id, g, c, q, book, f"rep:{tag}:{f.id}:{g}:{c}")
                            stats["replenished"] += q
            if s.type == "blood_bank":
                for g in ABO_RH:
                    for c in ("RBC", "PLT", "FFP"):
                        lam, _ = demand_rate(s, g, c, today, fests, inc)
                        q = int(rng.poisson(lam * 4 * hours / 24))
                        if q:
                            await _receive(session, f.id, g, c, q, book, f"camp:{tag}:{f.id}:{g}:{c}")
                            stats["received"] += q
        await session.commit()
    return stats


async def _receive(session, fid: int, g: str, c: str, q: int, book, key: str) -> None:
    shelf = book.shelf[c].shelf_life_hours
    now = now_utc()
    ev = InventoryEventIn(type="receive", facility_id=fid, abo_rh=g, component=c, quantity=min(q, 200),
                          collected_at=now - timedelta(hours=6), expires_at=now - timedelta(hours=6) + timedelta(hours=shelf))
    await record_event(session, SIM_ACTOR, ev, key, source="api")

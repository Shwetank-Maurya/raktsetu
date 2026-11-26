"""The inventory ledger. The ONLY module allowed to change blood_units.status.

Every mutation appends an inventory_events row in the same transaction. Idempotency is enforced
by the unique (facility_id, idempotency_key) index: the event row is inserted first, so a
concurrent duplicate blocks on the index and then returns the original result.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BloodUnit, ConsumptionDaily, Facility, InventoryEvent
from app.domain.audit import audit
from app.domain.errors import Conflict, InsufficientStock, NotFound
from app.domain.rules import DEFAULT_SHELF_LIFE
from app.schemas import InventoryEventIn
from app.security import Principal

IST = ZoneInfo("Asia/Kolkata")
LIVE_STATUSES = ("available", "reserved", "quarantined", "in_transit")


def now_utc() -> datetime:
    return datetime.now(UTC)


async def _claim_key(
    session: AsyncSession, facility_id: int, key: str, etype: str, actor: Principal, source: str,
    event_time: datetime, **fields,
) -> tuple[InventoryEvent | None, dict | None]:
    """Insert the event row. Returns (new_event, None) or (None, previous_result) on duplicate."""
    stmt = (
        pg_insert(InventoryEvent)
        .values(idempotency_key=key, facility_id=facility_id, type=etype, actor_id=actor.uid,
                source=source, event_time=event_time, **fields)
        .on_conflict_do_nothing(constraint="uq_event_idem")
        .returning(InventoryEvent.id)
    )
    new_id = (await session.execute(stmt)).scalar_one_or_none()
    if new_id is None:
        prev = (await session.execute(
            select(InventoryEvent).where(InventoryEvent.facility_id == facility_id,
                                         InventoryEvent.idempotency_key == key)
        )).scalar_one()
        return None, (prev.payload or {}).get("result", {}) | {"duplicate": True, "event_id": prev.id}
    return await session.get(InventoryEvent, new_id), None


async def _set_status(session: AsyncSession, units: Sequence[BloodUnit], status: str, **extra) -> None:
    for u in units:
        u.status = status
        u.version += 1
        for k, v in extra.items():
            setattr(u, k, v)
    await session.flush()


async def _fefo_pick(
    session: AsyncSession, facility_id: int, abo_rh: str, component: str, n: int,
    statuses: tuple[str, ...] = ("available",), min_usable_h: float | None = None,
) -> list[BloodUnit]:
    """Lock and return the n earliest-expiring usable units (First-Expiry-First-Out)."""
    if min_usable_h is None:
        min_usable_h = DEFAULT_SHELF_LIFE[component].min_usable_hours
    cutoff = now_utc() + timedelta(hours=min_usable_h)
    q = (
        select(BloodUnit)
        .where(BloodUnit.facility_id == facility_id, BloodUnit.abo_rh == abo_rh,
               BloodUnit.component == component, BloodUnit.status.in_(statuses),
               BloodUnit.expires_at > cutoff)
        .order_by(BloodUnit.expires_at)
        .limit(n)
        .with_for_update(skip_locked=True)
    )
    return list((await session.execute(q)).scalars().all())


async def _lock_units(session: AsyncSession, facility_id: int, unit_ids: list[str]) -> list[BloodUnit]:
    q = select(BloodUnit).where(BloodUnit.id.in_(unit_ids)).with_for_update()
    units = list((await session.execute(q)).scalars().all())
    if len(units) != len(set(unit_ids)):
        raise NotFound("some unit_ids do not exist", missing=sorted(set(unit_ids) - {u.id for u in units}))
    if any(u.facility_id != facility_id for u in units):
        raise Conflict("unit belongs to another facility")
    return units


async def _bump_consumption(session: AsyncSession, units: Sequence[BloodUnit], when: datetime,
                            emergency: bool) -> None:
    day = when.astimezone(IST).date()
    counts: dict[tuple[int, str, str], int] = {}
    for u in units:
        counts[(u.facility_id, u.abo_rh, u.component)] = counts.get((u.facility_id, u.abo_rh, u.component), 0) + 1
    for (fid, g, c), n in counts.items():
        # units_scheduled is reserved for known cohort demand (thalassemia); ad-hoc issues are statistical.
        stmt = pg_insert(ConsumptionDaily).values(
            facility_id=fid, date=day, abo_rh=g, component=c, units_issued=n,
            units_emergency=n if emergency else 0, units_scheduled=0,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["facility_id", "date", "abo_rh", "component"],
            set_={
                "units_issued": ConsumptionDaily.units_issued + n,
                "units_emergency": ConsumptionDaily.units_emergency + (n if emergency else 0),
            },
        )
        await session.execute(stmt)


async def record_event(
    session: AsyncSession, actor: Principal, ev: InventoryEventIn, idempotency_key: str, source: str = "api",
) -> dict:
    facility = await session.get(Facility, ev.facility_id)
    if facility is None or not facility.active:
        raise NotFound("facility not found or inactive")
    event_time = ev.event_time or now_utc()
    event, prev = await _claim_key(
        session, ev.facility_id, idempotency_key, ev.type, actor, source, event_time,
        abo_rh=ev.abo_rh, component=ev.component, quantity=ev.quantity,
    )
    if prev is not None:
        return prev

    result: dict
    if ev.type == "receive":
        donation = ev.donation_id or f"D-{uuid.uuid4().hex[:10].upper()}"
        units = [
            BloodUnit(
                donation_id=donation if ev.quantity == 1 else f"{donation}-{i + 1}",
                facility_id=ev.facility_id, abo_rh=ev.abo_rh, component=ev.component,
                irradiated=ev.attributes.irradiated, leukoreduced=ev.attributes.leukoreduced,
                cmv_safe=ev.attributes.cmv_safe, collected_at=ev.collected_at, expires_at=ev.expires_at,
                volume_ml=ev.volume_ml, status="available",
            )
            for i in range(ev.quantity)
        ]
        session.add_all(units)
        await session.flush()
        result = {"unit_ids": [u.id for u in units], "count": len(units)}

    elif ev.type == "issue":
        if ev.unit_ids:
            units = await _lock_units(session, ev.facility_id, ev.unit_ids)
            bad = [u.id for u in units if u.status not in ("available", "reserved")]
            if bad:
                raise Conflict("units not issuable", unit_ids=bad)
        else:
            units = await _fefo_pick(session, ev.facility_id, ev.abo_rh, ev.component, ev.quantity)
            if len(units) < ev.quantity:
                raise InsufficientStock(f"only {len(units)} usable {ev.abo_rh} {ev.component} units",
                                        available=len(units))
        await _set_status(session, units, "issued", reservation_id=None)
        await _bump_consumption(session, units, event_time, ev.emergency)
        result = {"unit_ids": [u.id for u in units], "count": len(units)}

    elif ev.type == "discard":
        if ev.unit_ids:
            units = await _lock_units(session, ev.facility_id, ev.unit_ids)
        else:
            units = await _fefo_pick(session, ev.facility_id, ev.abo_rh, ev.component, ev.quantity,
                                     statuses=("available", "quarantined"), min_usable_h=-1e6)
        units = [u for u in units if u.status in LIVE_STATUSES and u.status != "in_transit"]
        await _set_status(session, units, "discarded", reservation_id=None)
        result = {"unit_ids": [u.id for u in units], "count": len(units)}

    elif ev.type == "quarantine":
        units = await _lock_units(session, ev.facility_id, ev.unit_ids or [])
        units = [u for u in units if u.status in ("available", "reserved")]
        await _set_status(session, units, "quarantined", reservation_id=None)
        result = {"unit_ids": [u.id for u in units], "count": len(units)}

    elif ev.type == "release_quarantine":
        units = await _lock_units(session, ev.facility_id, ev.unit_ids or [])
        units = [u for u in units if u.status == "quarantined" and u.expires_at > now_utc()]
        await _set_status(session, units, "available")
        result = {"unit_ids": [u.id for u in units], "count": len(units)}

    elif ev.type == "recall":
        # A recall blocks every component made from the donation, at every facility.
        base = ev.donation_id
        q = (select(BloodUnit)
             .where((BloodUnit.donation_id == base) | BloodUnit.donation_id.like(f"{base}-%"),
                    BloodUnit.status.in_(("available", "reserved", "in_transit")))
             .with_for_update())
        units = list((await session.execute(q)).scalars().all())
        await _set_status(session, units, "quarantined", reservation_id=None)
        result = {"unit_ids": [u.id for u in units], "count": len(units),
                  "facilities": sorted({u.facility_id for u in units})}
    else:  # pragma: no cover - guarded by schema
        raise Conflict(f"unsupported event type {ev.type}")

    event.payload = {"request": ev.model_dump(mode="json"), "result": result}
    event.quantity = result.get("count", ev.quantity)
    facility.last_reported_at = now_utc()
    await audit(session, actor, f"inventory.{ev.type}", "facility", ev.facility_id,
                after={"count": result.get("count"), "abo_rh": ev.abo_rh, "component": ev.component})
    await session.flush()
    return result | {"event_id": event.id, "duplicate": False}


async def system_event(session: AsyncSession, facility_id: int, etype: str, units: Sequence[BloodUnit],
                       key: str, payload: dict | None = None) -> None:
    """Ledger entry for system-driven transitions (expiry sweep, transfers, reservations)."""
    from app.security import SYSTEM

    await _claim_key(session, facility_id, key, etype, SYSTEM, "system", now_utc(),
                     quantity=len(units), payload={"unit_ids": [u.id for u in units]} | (payload or {}))


async def sweep_expired(session: AsyncSession) -> int:
    """Mark units past expiry as expired (nightly job + every cycle). Returns count."""
    now = now_utc()
    q = (select(BloodUnit)
         .where(BloodUnit.status.in_(("available", "reserved", "quarantined")), BloodUnit.expires_at <= now)
         .with_for_update(skip_locked=True))
    units = list((await session.execute(q)).scalars().all())
    by_fac: dict[int, list[BloodUnit]] = {}
    for u in units:
        by_fac.setdefault(u.facility_id, []).append(u)
    await _set_status(session, units, "expired", reservation_id=None)
    for fid, us in by_fac.items():
        await system_event(session, fid, "expire", us, f"expire:{fid}:{now.isoformat()}")
    return len(units)


async def move_units(session: AsyncSession, unit_ids: list[str], status: str, **extra) -> int:
    """Bulk status change used by the transfer state machine (which writes its own events)."""
    if not unit_ids:
        return 0
    res = await session.execute(
        update(BloodUnit).where(BloodUnit.id.in_(unit_ids))
        .values(status=status, version=BloodUnit.version + 1, **extra)
    )
    return res.rowcount or 0

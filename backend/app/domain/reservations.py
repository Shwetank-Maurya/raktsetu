"""Reservations with TTL. Row locks with SKIP LOCKED guarantee that N concurrent requests for the
last units can never double-allocate: each transaction locks disjoint rows or fails."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BloodUnit, Reservation
from app.domain.audit import audit
from app.domain.errors import InsufficientStock, InvalidTransition, NotFound
from app.domain.ledger import _fefo_pick, _set_status, now_utc, system_event
from app.schemas import ReservationIn
from app.security import Principal


async def reserve(session: AsyncSession, actor: Principal, req: ReservationIn) -> Reservation:
    units = await _fefo_pick(session, req.facility_id, req.abo_rh, req.component, req.quantity)
    if len(units) < req.quantity:
        raise InsufficientStock(
            f"only {len(units)} unlocked usable {req.abo_rh} {req.component} units", available=len(units)
        )
    res = Reservation(
        facility_id=req.facility_id, abo_rh=req.abo_rh, component=req.component, quantity=req.quantity,
        unit_ids=[u.id for u in units], purpose=req.purpose, created_by=actor.uid,
        expires_at=now_utc() + timedelta(minutes=req.ttl_minutes),
    )
    session.add(res)
    await session.flush()
    await _set_status(session, units, "reserved", reservation_id=res.id)
    await system_event(session, req.facility_id, "reserve", units, f"reserve:{res.id}", {"reservation_id": res.id})
    await audit(session, actor, "reservation.create", "reservation", res.id, after={"quantity": req.quantity})
    return res


async def release(session: AsyncSession, actor: Principal, reservation_id: str, reason: str = "released") -> Reservation:
    res = await session.get(Reservation, reservation_id, with_for_update=True)
    if res is None:
        raise NotFound("reservation not found")
    if res.status != "active":
        raise InvalidTransition(f"reservation is {res.status}")
    units = list((await session.execute(
        select(BloodUnit).where(BloodUnit.reservation_id == res.id, BloodUnit.status == "reserved").with_for_update()
    )).scalars().all())
    await _set_status(session, units, "available", reservation_id=None)
    res.status = "expired" if reason == "ttl" else "released"
    await system_event(session, res.facility_id, "release", units, f"release:{res.id}", {"reason": reason})
    await audit(session, actor, f"reservation.{res.status}", "reservation", res.id)
    return res


async def release_expired(session: AsyncSession) -> int:
    from app.security import SYSTEM

    ids = (await session.execute(
        select(Reservation.id).where(Reservation.status == "active", Reservation.expires_at <= now_utc())
    )).scalars().all()
    for rid in ids:
        await release(session, SYSTEM, rid, reason="ttl")
    return len(ids)

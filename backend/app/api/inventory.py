from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BloodUnit, Facility, RejectedEntry
from app.db.session import get_session
from app.deps import current_user, idempotency_key, idempotent
from app.domain import ledger, reservations
from app.domain.compat import load_rulebook
from app.domain.ledger import now_utc
from app.domain.stock import freshness_hours, status_counts, usable_counts
from app.schemas import InventoryEventIn, ReservationIn
from app.security import Principal
from app.services import realtime
from app.services.scope import allowed_facilities, assert_facility, require_role

router = APIRouter(prefix="/api", tags=["inventory"])


@router.post("/inventory/events")
async def post_event(
    body: dict = Body(..., examples=[{"type": "receive", "facility_id": 1, "abo_rh": "O-", "component": "RBC", "quantity": 2}]),
    key: str = Depends(idempotency_key), session: AsyncSession = Depends(get_session),
    p: Principal = Depends(current_user),
) -> dict:
    """Append to the ledger. Invalid entries get 422 with a reason and are kept in rejected_entries."""
    require_role(p, "bank_manager", "hospital_user", "regional_coordinator")
    try:
        ev = InventoryEventIn.model_validate(body)
    except ValidationError as exc:
        session.add(RejectedEntry(facility_id=body.get("facility_id") if isinstance(body.get("facility_id"), int) else None,
                                  source="api", reason="; ".join(e["msg"] for e in exc.errors()), payload=body))
        await session.commit()
        raise HTTPException(422, [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]) from exc
    await assert_facility(session, p, ev.facility_id)
    result = await ledger.record_event(session, p, ev, key, source=body.get("source", "ui") if body.get("source") in ("ui", "api") else "api")
    await session.commit()
    realtime.mirror_event("stock", {"facility_id": ev.facility_id})
    return result


@router.get("/inventory/matrix")
async def matrix(region_id: int | None = None, session: AsyncSession = Depends(get_session),
                 p: Principal = Depends(current_user)) -> dict:
    """Group x component x facility availability with freshness badges."""
    allowed = await allowed_facilities(session, p)
    q = select(Facility).where(Facility.active.is_(True)).order_by(Facility.code)
    facs = [f for f in (await session.execute(q)).scalars()
            if (allowed is None or f.id in allowed) and (region_id is None or f.region_id == region_id)]
    ids = {f.id for f in facs}
    book = await load_rulebook(session)
    usable = await usable_counts(session, book, ids)
    statuses = await status_counts(session, ids)
    rows = []
    for f in facs:
        cells = {}
        for (fid, g, c), v in statuses.items():
            if fid == f.id:
                cells[f"{g}|{c}"] = {"usable": usable.get((fid, g, c), 0), **v}
        rows.append({"facility_id": f.id, "code": f.code, "name": f.name, "type": f.type, "region_id": f.region_id,
                     "freshness_h": round(freshness_hours(f), 1) if f.last_reported_at else None, "cells": cells})
    return {"as_of": now_utc().isoformat(), "facilities": rows}


@router.get("/inventory/expiring")
async def expiring(hours: int = Query(72, ge=1, le=24 * 30), facility_id: int | None = None,
                   session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    """Expiry buckets and use-it-or-move-it candidates (FEFO)."""
    allowed = await allowed_facilities(session, p)
    now = now_utc()
    q = (select(BloodUnit).where(BloodUnit.status == "available", BloodUnit.expires_at <= now + timedelta(hours=hours),
                                 BloodUnit.expires_at > now).order_by(BloodUnit.expires_at))
    if facility_id:
        await assert_facility(session, p, facility_id)
        q = q.where(BloodUnit.facility_id == facility_id)
    elif allowed is not None:
        q = q.where(BloodUnit.facility_id.in_(allowed or {-1}))
    units = (await session.execute(q.limit(2000))).scalars().all()
    facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    buckets = {"<24h": 0, "24-48h": 0, "48-72h": 0, ">72h": 0}
    groups: dict[tuple, dict] = {}
    for u in units:
        h = (u.expires_at - now).total_seconds() / 3600
        b = "<24h" if h < 24 else "24-48h" if h < 48 else "48-72h" if h < 72 else ">72h"
        buckets[b] += 1
        k = (u.facility_id, u.abo_rh, u.component)
        g = groups.setdefault(k, {"facility_id": u.facility_id, "facility_name": facs[u.facility_id].name,
                                  "abo_rh": u.abo_rh, "component": u.component, "units": 0, "earliest_expiry_h": h,
                                  "unit_ids": []})
        g["units"] += 1
        g["unit_ids"].append(u.id)
        g["earliest_expiry_h"] = min(g["earliest_expiry_h"], h)
    items = sorted(groups.values(), key=lambda x: x["earliest_expiry_h"])
    for it in items:
        it["earliest_expiry_h"] = round(it["earliest_expiry_h"], 1)
        it["unit_ids"] = it["unit_ids"][:50]
    return {"as_of": now.isoformat(), "hours": hours, "buckets": buckets, "groups": items}


@router.get("/inventory/units")
async def units(facility_id: int, abo_rh: str | None = None, component: str | None = None,
                status: str = "available", session: AsyncSession = Depends(get_session),
                p: Principal = Depends(current_user)) -> list[dict]:
    await assert_facility(session, p, facility_id)
    q = select(BloodUnit).where(BloodUnit.facility_id == facility_id, BloodUnit.status == status)
    if abo_rh:
        q = q.where(BloodUnit.abo_rh == abo_rh)
    if component:
        q = q.where(BloodUnit.component == component)
    rows = (await session.execute(q.order_by(BloodUnit.expires_at).limit(500))).scalars().all()
    return [{"id": u.id, "donation_id": u.donation_id, "abo_rh": u.abo_rh, "component": u.component,
             "expires_at": u.expires_at, "status": u.status, "irradiated": u.irradiated, "cmv_safe": u.cmv_safe,
             "leukoreduced": u.leukoreduced} for u in rows]


@router.post("/reservations")
async def create_reservation(body: ReservationIn, key: str = Depends(idempotency_key),
                             session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    require_role(p, "hospital_user", "bank_manager", "regional_coordinator")
    await assert_facility(session, p, body.facility_id)

    async def run():
        r = await reservations.reserve(session, p, body)
        return {"id": r.id, "unit_ids": r.unit_ids, "expires_at": r.expires_at, "status": r.status}

    out = await idempotent(session, "reserve", p, key, run)
    realtime.mirror_event("stock", {"facility_id": body.facility_id})
    return out


@router.post("/reservations/{reservation_id}/release")
async def release_reservation(reservation_id: str, key: str = Depends(idempotency_key),
                              session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    async def run():
        from app.db.models import Reservation

        res = await session.get(Reservation, reservation_id)
        if res is None:
            raise HTTPException(404, "reservation not found")
        await assert_facility(session, p, res.facility_id)
        r = await reservations.release(session, p, reservation_id)
        return {"id": r.id, "status": r.status}

    return await idempotent(session, "release", p, key, run)

"""Compatibility-aware availability search ranked by ETA and remaining shelf life."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BloodUnit, Facility
from app.domain.compat import RuleBook
from app.domain.ledger import now_utc
from app.domain.stock import freshness_hours
from app.optimizer.routes import fallback_eta


async def search(
    session: AsyncSession, book: RuleBook, abo_rh: str, component: str, lat: float, lng: float,
    radius_km: float = 50, include_compatible: bool = True, exclude_facility: int | None = None,
    irradiated: bool = False, cmv_safe: bool = False, limit: int = 20,
) -> list[dict]:
    groups = book.donors_for(component, abo_rh) if include_compatible else [abo_rh]
    shelf = book.shelf[component]
    now = now_utc()
    q = (select(BloodUnit.facility_id, BloodUnit.abo_rh, func.count(), func.min(BloodUnit.expires_at),
                func.max(BloodUnit.expires_at))
         .where(BloodUnit.status == "available", BloodUnit.component == component, BloodUnit.abo_rh.in_(groups),
                BloodUnit.expires_at > now + timedelta(hours=shelf.min_usable_hours))
         .group_by(BloodUnit.facility_id, BloodUnit.abo_rh))
    if irradiated:
        q = q.where(BloodUnit.irradiated.is_(True))  # special-attribute pools (edge case #14)
    if cmv_safe:
        q = q.where(BloodUnit.cmv_safe.is_(True))
    facs = {f.id: f for f in (await session.execute(select(Facility).where(Facility.active.is_(True)))).scalars()}
    out = []
    for fid, g, n, min_exp, max_exp in (await session.execute(q)).all():
        f = facs.get(fid)
        if f is None or fid == exclude_facility:
            continue
        minutes, km = fallback_eta((lat, lng), (f.lat, f.lng))
        if km > radius_km * 1.35:
            continue
        out.append({
            "facility_id": fid, "facility_name": f.name, "facility_code": f.code, "type": f.type,
            "abo_rh": g, "component": component, "units": n, "exact_match": g == abo_rh,
            "needs_clinician_approval": g != abo_rh,
            "eta_minutes": round(minutes, 0), "distance_km": round(km, 1),
            "earliest_expiry_h": round((min_exp - now).total_seconds() / 3600, 1),
            "latest_expiry_h": round((max_exp - now).total_seconds() / 3600, 1),
            "freshness_h": round(freshness_hours(f) or 0, 1), "lat": f.lat, "lng": f.lng,
        })
    out.sort(key=lambda r: (not r["exact_match"], r["eta_minutes"], -r["latest_expiry_h"]))
    return out[:limit]

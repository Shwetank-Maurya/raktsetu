"""Runs the optimizer on the latest risk picture and persists proposals."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Facility, TransferRequest
from app.domain.compat import RuleBook
from app.domain.stock import expiry_profiles
from app.optimizer.allocate import Params, PlanResult, SeriesState, plan
from app.optimizer.routes import eta_matrix
from app.services.risk import incoming_by_series


async def facility_eta(session: AsyncSession, facs: list[Facility], use_api: bool = True) -> dict[tuple[int, int], tuple[float, float, str]]:
    pts = [(f.lat, f.lng) for f in facs]
    m = await eta_matrix(pts, pts, use_api=use_api)
    return {(facs[i].id, facs[j].id): v for (i, j), v in m.items() if i != j}


def states_from_risk(risk_rows: list[dict], profiles: dict, incoming: dict, facs: dict[int, Facility]) -> dict:
    states: dict[tuple[int, str, str], SeriesState] = {}
    for r in risk_rows:
        key = (r["facility_id"], r["abo_rh"], r["component"])
        f = facs.get(r["facility_id"])
        if f is None:
            continue
        hours = list(profiles.get(key, []))
        # Count already-approved inbound units as stock so the plan does not double-ship.
        hours += [life for _, life in incoming.get(key, [])]
        hours.sort()
        states[key] = SeriesState(
            facility_id=key[0], abo_rh=key[1], component=key[2], usable_hours=hours,
            daily_q50=r.get("daily_q50", r.get("mean_daily_demand", 0.0)), daily_q90=r.get("daily_q90", 0.0),
            severity=r["severity"], p24=r["p_stockout_24"], tts_p50=r["tts_p50"],
            expected_wastage=r["expected_wastage"], is_bank=f.type == "blood_bank",
        )
    return states


async def build_plan(session: AsyncSession, book: RuleBook, risk_rows: list[dict], include_substitutes: bool = True,
                     region_facilities: set[int] | None = None, use_api: bool = True,
                     params: Params | None = None) -> tuple[PlanResult, dict[int, Facility]]:
    facs_all = (await session.execute(select(Facility).where(Facility.active.is_(True)).order_by(Facility.id))).scalars().all()
    facs = [f for f in facs_all if region_facilities is None or f.id in region_facilities]
    fmap = {f.id: f for f in facs}
    profiles = await expiry_profiles(session, book, set(fmap))
    incoming = await incoming_by_series(session, book)
    states = states_from_risk([r for r in risk_rows if r["facility_id"] in fmap], profiles, incoming, fmap)
    eta = await facility_eta(session, facs, use_api=use_api)
    existing = (await session.execute(
        select(TransferRequest).where(TransferRequest.status == "proposed")
    )).scalars().all()
    stable = {(t.from_facility_id, t.to_facility_id, t.abo_rh, t.component) for t in existing}
    result = plan(states, eta, book, params, stable, include_substitutes)
    return result, fmap


async def persist_plan(session: AsyncSession, result: PlanResult, created_by: str = "optimizer") -> list[TransferRequest]:
    plan_id = str(uuid.uuid4())
    await session.execute(
        update(TransferRequest).where(TransferRequest.status == "proposed").values(status="superseded")
    )
    rows = []
    for p in result.proposals:
        t = TransferRequest(
            plan_id=plan_id, kind=p.kind, from_facility_id=p.from_facility_id, to_facility_id=p.to_facility_id,
            abo_rh=p.abo_rh, component=p.component, requested_for_abo_rh=p.requested_for_abo_rh,
            quantity=p.quantity, unit_ids=[], status="proposed", eta_minutes=p.eta_minutes,
            distance_km=p.distance_km, eta_source=p.eta_source, min_life_on_arrival_h=p.min_life_on_arrival_h,
            needs_clinician_approval=p.needs_clinician_approval, reason_json=p.reason, created_by=created_by,
        )
        session.add(t)
        rows.append(t)
    await session.flush()
    return rows

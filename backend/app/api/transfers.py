import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.features import explain_transfer
from app.db.models import Facility, TransferRequest
from app.db.session import get_session
from app.deps import current_user, idempotency_key, idempotent
from app.domain import transfers as tx
from app.domain.audit import audit
from app.domain.compat import load_rulebook
from app.domain.errors import Forbidden
from app.optimizer.routes import eta_matrix
from app.schemas import ManualTransferIn, PlanIn, TransferAction
from app.security import Principal
from app.services import realtime
from app.services.planning import build_plan, persist_plan
from app.services.risk import latest_risk
from app.services.scope import allowed_facilities, assert_facility, region_subtree, require_role

router = APIRouter(prefix="/api/transfers", tags=["transfers"])


def _t(t: TransferRequest, facs: dict[int, Facility]) -> dict:
    fr, to = facs.get(t.from_facility_id), facs.get(t.to_facility_id)
    return {"id": t.id, "plan_id": t.plan_id, "kind": t.kind, "status": t.status,
            "from_facility_id": t.from_facility_id, "from_name": fr.name if fr else None,
            "from_lat": fr.lat if fr else None, "from_lng": fr.lng if fr else None,
            "to_facility_id": t.to_facility_id, "to_name": to.name if to else None,
            "to_lat": to.lat if to else None, "to_lng": to.lng if to else None,
            "abo_rh": t.abo_rh, "component": t.component, "requested_for_abo_rh": t.requested_for_abo_rh,
            "quantity": t.quantity, "unit_ids": t.unit_ids, "eta_minutes": t.eta_minutes, "distance_km": t.distance_km,
            "eta_source": t.eta_source, "min_life_on_arrival_h": t.min_life_on_arrival_h,
            "needs_clinician_approval": t.needs_clinician_approval, "flagged_for_review": t.flagged_for_review,
            "reason": t.reason_json, "created_by": t.created_by, "approved_by": t.approved_by,
            "created_at": t.created_at, "updated_at": t.updated_at, "dispatched_at": t.dispatched_at,
            "received_at": t.received_at}


async def _facs(session: AsyncSession) -> dict[int, Facility]:
    return {f.id: f for f in (await session.execute(select(Facility))).scalars()}


@router.get("")
async def list_transfers(status: str | None = Query(None, description="comma-separated"), limit: int = Query(100, le=500),
                         session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> list[dict]:
    allowed = await allowed_facilities(session, p)
    q = select(TransferRequest).order_by(TransferRequest.id.desc())
    if status:
        q = q.where(TransferRequest.status.in_(status.split(",")))
    if allowed is not None:
        ids = allowed or {-1}
        q = q.where(or_(TransferRequest.from_facility_id.in_(ids), TransferRequest.to_facility_id.in_(ids)))
    facs = await _facs(session)
    return [_t(t, facs) for t in (await session.execute(q.limit(limit))).scalars()]


@router.post("/plan")
async def plan(body: PlanIn, key: str = Depends(idempotency_key), session: AsyncSession = Depends(get_session),
               p: Principal = Depends(current_user)) -> dict:
    """Run the optimizer now for a region (also runs hourly in the scheduled cycle)."""
    require_role(p, "regional_coordinator")

    async def run():
        book = await load_rulebook(session)
        region_facs = None
        if body.region_id:
            regions = await region_subtree(session, body.region_id)
            region_facs = {f.id for f in (await _facs(session)).values() if f.region_id in regions}
        from app.db.models import DemandForecast
        from app.ml.risk_sim import expected_demand

        rows = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in await latest_risk(session)]
        fc: dict = {}
        for f in (await session.execute(select(DemandForecast).order_by(DemandForecast.target_date))).scalars():
            fc.setdefault((f.facility_id, f.abo_rh, f.component), f)  # first (nearest) forecast day
        for r in rows:
            f = fc.get((r["facility_id"], r["abo_rh"], r["component"]))
            mean = (f.mean if f.mean is not None else float(expected_demand(f.q10, f.q50, f.q90))) + f.scheduled_units if f else 0.0
            r["daily_q50"], r["daily_q90"] = mean, max(f.q90, mean) if f else 0.0
        result, _ = await build_plan(session, book, rows, body.include_substitutes, region_facs)
        saved = await persist_plan(session, result, created_by=p.uid)
        await audit(session, p, "transfer.plan", "plan", saved[0].plan_id if saved else "empty", after=result.stats)
        facs = await _facs(session)
        return {"stats": result.stats, "deficits": result.deficits, "proposals": [_t(t, facs) for t in saved]}

    out = await idempotent(session, "plan", p, key, run)
    realtime.mirror_event("transfers", {"action": "plan"})
    return out


@router.post("")
async def manual_request(body: ManualTransferIn, key: str = Depends(idempotency_key),
                         session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    """A facility asks for units. Requests above 2x the forecast need are flagged for review (edge case #26)."""
    await assert_facility(session, p, body.to_facility_id)

    async def run():
        facs = await _facs(session)
        fr, to = facs[body.from_facility_id], facs[body.to_facility_id]
        m = await eta_matrix([(fr.lat, fr.lng)], [(to.lat, to.lng)])
        minutes, km, src = m[(0, 0)]
        risk = [r for r in await latest_risk(session, {to.id}) if r.abo_rh == body.abo_rh and r.component == body.component]
        need = max(1, math.ceil(risk[0].days_cover and (risk[0].usable_units / max(risk[0].days_cover, 0.01)) * 3)) if risk else 1
        flagged = body.quantity > 2 * need
        book = await load_rulebook(session)
        t = TransferRequest(
            kind="manual", from_facility_id=fr.id, to_facility_id=to.id, abo_rh=body.abo_rh, component=body.component,
            quantity=body.quantity, status="proposed", eta_minutes=round(minutes, 1), distance_km=round(km, 2),
            eta_source=src, min_life_on_arrival_h=book.shelf[body.component].min_life_on_arrival_hours,
            flagged_for_review=flagged, created_by=p.uid,
            reason_json={"manual_reason": body.reason, "forecast_need_3d": need,
                         "flag": "request exceeds 2x forecast need - review" if flagged else None},
        )
        session.add(t)
        await session.flush()
        await audit(session, p, "transfer.request", "transfer", t.id, after={"quantity": t.quantity, "flagged": flagged})
        return _t(t, facs)

    return await idempotent(session, "transfer-request", p, key, run)


async def _transition(action: str, transfer_id: int, body: TransferAction, key: str, session: AsyncSession, p: Principal) -> dict:
    async def run():
        book = await load_rulebook(session)
        if action == "approve":
            t = await tx.approve(session, p, transfer_id, book, clinician_ack=body.clinician_ack)
        elif action == "reject":
            t = await tx.reject(session, p, transfer_id, body.note)
        elif action == "dispatch":
            t = await tx.dispatch(session, p, transfer_id)
        elif action == "receive":
            t = await tx.receive(session, p, transfer_id)
        elif action == "cancel":
            t = await tx.cancel(session, p, transfer_id, body.note or "cancelled")
        else:  # pragma: no cover
            raise HTTPException(404)
        await session.flush()
        await session.refresh(t)  # onupdate columns are expired after UPDATE; load them async
        return _t(t, await _facs(session))

    if p.role == "hospital_user" and action in ("approve", "reject", "dispatch"):
        raise Forbidden("hospital users cannot approve or dispatch transfers")
    out = await idempotent(session, f"transfer-{action}:{transfer_id}", p, key, run)
    realtime.mirror_event("transfers", {"action": action, "id": transfer_id})
    realtime.mirror_event("stock", {"transfer_id": transfer_id})
    return out


@router.post("/{transfer_id}/approve")
async def approve(transfer_id: int, body: TransferAction = TransferAction(), key: str = Depends(idempotency_key),
                  session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _transition("approve", transfer_id, body, key, session, p)


@router.post("/{transfer_id}/reject")
async def reject(transfer_id: int, body: TransferAction = TransferAction(), key: str = Depends(idempotency_key),
                 session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _transition("reject", transfer_id, body, key, session, p)


@router.post("/{transfer_id}/dispatch")
async def dispatch(transfer_id: int, body: TransferAction = TransferAction(), key: str = Depends(idempotency_key),
                   session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _transition("dispatch", transfer_id, body, key, session, p)


@router.post("/{transfer_id}/receive")
async def receive(transfer_id: int, body: TransferAction = TransferAction(), key: str = Depends(idempotency_key),
                  session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _transition("receive", transfer_id, body, key, session, p)


@router.post("/{transfer_id}/cancel")
async def cancel(transfer_id: int, body: TransferAction = TransferAction(), key: str = Depends(idempotency_key),
                 session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _transition("cancel", transfer_id, body, key, session, p)


@router.get("/{transfer_id}/explain")
async def explain(transfer_id: int, lang: str = Query("en", pattern="^(en|hi)$"),
                  session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    t = await session.get(TransferRequest, transfer_id)
    if t is None:
        raise HTTPException(404, "transfer not found")
    allowed = await allowed_facilities(session, p)
    if allowed is not None and t.from_facility_id not in allowed and t.to_facility_id not in allowed:
        raise Forbidden("transfer outside your scope")
    return await explain_transfer(session, t, lang)

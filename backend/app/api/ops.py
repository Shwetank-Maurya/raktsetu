"""Alerts, simulation, copilot, donors, register OCR, evaluation, data quality, internal jobs."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import copilot
from app.ai.features import draft_campaign, extract_register, review_rows
from app.ai.gemini_client import GeminiUnavailable
from app.db.models import Alert, AppConfig, AuditLog, ConsumptionDaily, EvalResult, Facility, JobRun, RejectedEntry
from app.db.session import get_session
from app.deps import current_user, idempotency_key, idempotent, internal_auth
from app.domain import ledger
from app.domain.audit import audit
from app.domain.compat import load_rulebook
from app.domain.stock import freshness_hours
from app.schemas import AlertAck, CampaignIn, CopilotIn, IncidentIn, InventoryEventIn, RegisterCommitIn
from app.security import Principal
from app.services import realtime
from app.services.incident import DEFAULT_ASSUMPTIONS, get_assumptions, simulate_incident
from app.services.scope import allowed_facilities, assert_facility, require_role

router = APIRouter()


# ----------------------------------------------------------------------------- alerts
@router.get("/api/alerts", tags=["alerts"])
async def list_alerts(status: str = Query("open,ack"), limit: int = Query(100, le=500),
                      session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> list[dict]:
    allowed = await allowed_facilities(session, p)
    q = select(Alert).where(Alert.status.in_(status.split(","))).order_by(Alert.last_fired_at.desc())
    if allowed is not None:
        q = q.where(Alert.facility_id.in_(allowed or {-1}))
    order = {"critical": 0, "high": 1, "warning": 2, "info": 3}
    rows = sorted((await session.execute(q.limit(limit))).scalars().all(), key=lambda a: order.get(a.severity, 9))
    return [{"id": a.id, "kind": a.kind, "severity": a.severity, "status": a.status, "message": a.message,
             "facility_id": a.facility_id, "abo_rh": a.abo_rh, "component": a.component, "details": a.details,
             "first_seen": a.first_seen, "last_seen": a.last_seen, "escalated_at": a.escalated_at,
             "acknowledged_by": a.acknowledged_by} for a in rows]


@router.post("/api/alerts/{alert_id}/ack", tags=["alerts"])
async def ack(alert_id: int, body: AlertAck = AlertAck(), key: str = Depends(idempotency_key),
              session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    async def run():
        a = await session.get(Alert, alert_id)
        if a is None:
            raise HTTPException(404, "alert not found")
        if a.facility_id:
            await assert_facility(session, p, a.facility_id)
        if a.status == "open":
            a.status, a.acknowledged_by, a.acknowledged_at = "ack", p.uid, datetime.now(UTC)
            await audit(session, p, "alert.ack", "alert", a.id, after={"note": body.note})
        return {"id": a.id, "status": a.status}

    out = await idempotent(session, f"ack:{alert_id}", p, key, run)
    realtime.mirror_alert({"id": alert_id, "status": out.get("status")})
    return out


class PushSubscribe(BaseModel):
    token: str


@router.post("/api/push/subscribe", tags=["alerts"])
async def push_subscribe(body: PushSubscribe, p: Principal = Depends(current_user)) -> dict:
    """Subscribe a browser's FCM token to its region topic (High/Critical alerts only)."""
    from app.config import get_settings

    if not get_settings().fcm_enabled:
        return {"subscribed": False, "reason": "FCM disabled on server"}
    try:
        from firebase_admin import messaging

        from app.services.realtime import _firestore

        _firestore()  # ensures the firebase app is initialised
        topic = f"region-{p.region_id or 1}"
        messaging.subscribe_to_topic([body.token], topic)
        return {"subscribed": True, "topic": topic}
    except Exception as exc:  # noqa: BLE001
        return {"subscribed": False, "reason": str(exc)[:200]}


# ----------------------------------------------------------------------------- stress test
@router.post("/api/simulate/incident", tags=["simulate"])
async def incident(body: IncidentIn, session: AsyncSession = Depends(get_session),
                   p: Principal = Depends(current_user)) -> dict:
    require_role(p, "regional_coordinator")
    book = await load_rulebook(session)
    return await simulate_incident(session, book, body)


@router.get("/api/simulate/assumptions", tags=["simulate"])
async def assumptions(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await get_assumptions(session)


@router.put("/api/simulate/assumptions", tags=["simulate"])
async def set_assumptions(body: dict, session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    require_role(p, "regional_coordinator")
    merged = DEFAULT_ASSUMPTIONS | {k: v for k, v in body.items() if k in DEFAULT_ASSUMPTIONS}
    row = await session.get(AppConfig, "incident_assumptions")
    if row:
        row.value = merged
    else:
        session.add(AppConfig(key="incident_assumptions", value=merged))
    await audit(session, p, "config.incident_assumptions", "app_config", "incident_assumptions", after=merged)
    await session.commit()
    return merged


# ----------------------------------------------------------------------------- copilot
@router.post("/api/copilot/chat", tags=["copilot"])
async def chat(body: CopilotIn, session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await copilot.chat(session, p, body.message, body.language, body.history)


# ----------------------------------------------------------------------------- donors
@router.post("/api/donors/campaign/draft", tags=["donors"])
async def campaign(body: CampaignIn, session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    require_role(p, "bank_manager", "regional_coordinator")
    await assert_facility(session, p, body.facility_id)
    out = await draft_campaign(session, body.facility_id, body.abo_rh, body.component, body.radius_km,
                               body.language, body.max_donors)
    await audit(session, p, "donor.campaign_draft", "facility", body.facility_id,
                after={"abo_rh": body.abo_rh, "eligible": out["eligible_donors"]})
    await session.commit()
    return out


# ----------------------------------------------------------------------------- register OCR
MAX_IMAGE = 8 * 1024 * 1024


@router.post("/api/register/extract", tags=["register"])
async def register_extract(facility_id: int = Form(...), image: UploadFile = File(...),
                           session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    require_role(p, "bank_manager", "hospital_user")
    await assert_facility(session, p, facility_id)
    if image.content_type not in ("image/jpeg", "image/png", "image/webp", "image/heic"):
        raise HTTPException(415, "upload a JPEG, PNG, WEBP or HEIC photo")
    data = await image.read()
    if len(data) > MAX_IMAGE:
        raise HTTPException(413, "image too large (max 8 MB)")
    try:
        return await extract_register(session, data, image.content_type, facility_id)
    except GeminiUnavailable as exc:
        raise HTTPException(503, f"Gemini vision unavailable ({exc}); enter units manually instead") from exc


@router.post("/api/register/commit", tags=["register"])
async def register_commit(body: RegisterCommitIn, key: str = Depends(idempotency_key),
                          session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    """Commit human-reviewed rows. Re-validated server-side; blocked rows are refused."""
    require_role(p, "bank_manager", "hospital_user")
    await assert_facility(session, p, body.facility_id)
    review = await review_rows(session, [{k: v for k, v in r.items() if k not in ("low_confidence_fields", "issues", "blocks_commit", "row")}
                                         | {"confidence": {}} for r in body.rows], body.facility_id)
    if not review["can_commit"]:
        raise HTTPException(422, {"message": "some rows still have issues", "rows": review["rows"]})
    results = []
    for r in body.rows:
        col = datetime.fromisoformat(r["collected_on"]).replace(tzinfo=UTC) if r.get("collected_on") else None
        exp = (datetime.fromisoformat(r["expires_on"]).replace(tzinfo=UTC) + timedelta(hours=23, minutes=59)) if r.get("expires_on") else None
        ev = InventoryEventIn(type="receive", facility_id=body.facility_id, abo_rh=r["abo_rh"], component=r["component"],
                              quantity=int(r["quantity"]), donation_id=r.get("donation_id"), collected_at=col, expires_at=exp)
        row_key = f"ocr:{key}:" + hashlib.sha256(repr(sorted(r.items())).encode()).hexdigest()[:24]
        results.append(await ledger.record_event(session, p, ev, row_key, source="ocr"))
    await session.commit()
    realtime.mirror_event("stock", {"facility_id": body.facility_id})
    return {"committed_rows": len(results), "units": sum(x.get("count", 0) for x in results)}


# ----------------------------------------------------------------------------- evaluation & data quality
@router.get("/api/eval", tags=["evaluation"])
async def evaluation(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    out = {}
    for kind in ("backtest", "replay"):
        row = (await session.execute(select(EvalResult).where(EvalResult.kind == kind)
                                     .order_by(EvalResult.id.desc()).limit(1))).scalar_one_or_none()
        if row:
            payload = dict(row.payload)
            payload.pop("history_meta", None)
            out[kind] = payload | {"created_at": row.created_at}
    runs = (await session.execute(select(JobRun).order_by(JobRun.started_at.desc()).limit(10))).scalars().all()
    out["job_runs"] = [{"id": r.id, "kind": r.kind, "status": r.status, "started_at": r.started_at,
                        "finished_at": r.finished_at, "stats": r.stats} for r in runs]
    return out


@router.get("/api/data-quality", tags=["evaluation"])
async def data_quality(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    allowed = await allowed_facilities(session, p)
    facs = [f for f in (await session.execute(select(Facility).order_by(Facility.code))).scalars()
            if allowed is None or f.id in allowed]
    rejects = (await session.execute(select(RejectedEntry).order_by(RejectedEntry.id.desc()).limit(50))).scalars().all()
    since = datetime.now(UTC).date() - timedelta(days=30)
    q = (select(ConsumptionDaily.facility_id, func.count(func.distinct(ConsumptionDaily.date)),
                func.sum(case((ConsumptionDaily.data_quality == "late", 1), else_=0)),
                func.sum(case((ConsumptionDaily.is_event_day.is_(True), 1), else_=0)))
         .where(ConsumptionDaily.date >= since).group_by(ConsumptionDaily.facility_id))
    stats = {fid: (days, late or 0, ev or 0) for fid, days, late, ev in (await session.execute(q)).all()}
    audits = (await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(30))).scalars().all()
    return {
        "facilities": [{"id": f.id, "code": f.code, "name": f.name, "active": f.active,
                        "freshness_h": round(freshness_hours(f), 1) if f.last_reported_at else None,
                        "reported_days_30": stats.get(f.id, (0, 0, 0))[0], "late_rows_30": stats.get(f.id, (0, 0, 0))[1],
                        "event_days_30": stats.get(f.id, (0, 0, 0))[2]} for f in facs],
        "rejected_entries": [{"id": r.id, "facility_id": r.facility_id, "source": r.source, "reason": r.reason,
                              "payload": r.payload, "created_at": r.created_at} for r in rejects],
        "recent_audit": [{"actor": a.actor_id, "role": a.actor_role, "action": a.action, "entity": a.entity,
                          "entity_id": a.entity_id, "ts": a.ts} for a in audits] if p.is_network_role else [],
    }


# ----------------------------------------------------------------------------- internal jobs
@router.post("/internal/jobs/run-cycle", tags=["internal"])
async def run_cycle_endpoint(force_forecast: bool = False, caller: str = Depends(internal_auth)) -> dict:
    from app.services.cycle import run_cycle

    return await run_cycle(force_forecast=force_forecast, trigger=caller)


@router.post("/internal/jobs/world-tick", tags=["internal"])
async def world_tick_endpoint(hours: float = Query(1.0, gt=0, le=24), caller: str = Depends(internal_auth)) -> dict:
    """Demo only: advance the synthetic world (issues + donor camps) so the live demo stays realistic."""
    from app.sim.world import tick

    return await tick(hours)


@router.post("/api/admin/run-cycle", tags=["internal"])
async def admin_run_cycle(force_forecast: bool = False, p: Principal = Depends(current_user)) -> dict:
    require_role(p, "admin", "regional_coordinator")
    from app.services.cycle import run_cycle

    return await run_cycle(force_forecast=force_forecast, trigger=f"manual:{p.uid}")

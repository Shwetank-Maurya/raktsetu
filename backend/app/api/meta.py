from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import gemini_client, groq_client
from app.config import get_settings
from app.db.models import Facility, Region
from app.db.session import get_session
from app.deps import current_user
from app.domain.stock import freshness_hours
from app.security import DEMO_USERS, Principal, issue_demo_token
from app.services.scope import allowed_facilities

router = APIRouter()


@router.get("/healthz", tags=["meta"])
@router.get("/api/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok", "service": "raktsetu-api"}


@router.get("/readyz", tags=["meta"])
@router.get("/api/readyz", tags=["meta"])
async def readyz(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"database not ready: {exc.__class__.__name__}") from exc
    return {"status": "ready", "database": "ok"}


@router.get("/api/meta", tags=["meta"])
async def meta() -> dict:
    """Which Google integrations are live vs degraded (shown in the UI footer)."""
    s = get_settings()
    return {
        "env": s.env,
        "integrations": {
            "gemini": gemini_client.status(),
            "groq": groq_client.status(),
            "firebase_auth": bool(s.firebase_project_id) and s.auth_mode in ("firebase", "both"),
            "demo_auth": s.auth_mode in ("demo", "both"),
            "firestore_live_feed": s.firestore_enabled,
            "fcm_push": s.fcm_enabled,
            "routes_api": bool(s.maps_server_key),
            "google_calendar": bool(s.google_calendar_api_key),
            "bigquery_export": bool(s.bigquery_dataset),
            "or_tools": True,
        },
        "data": "synthetic - see docs/DATA_CARD.md",
        "disclaimer": "Decision support only. Not a medical device. Humans approve every transfer.",
    }


_SUMMARY_CACHE: dict = {"at": 0.0, "data": None}
SUMMARY_TTL_S = 60


@router.get("/api/public/summary", tags=["meta"])
async def public_summary(session: AsyncSession = Depends(get_session)) -> dict:
    """Unauthenticated landing-page snapshot: network-level aggregates only (no facility, unit or
    donor data), all derived from the synthetic demo network. Cached 60 s: it is the same for
    every visitor and costs ~12 round trips to a remote (Neon) database."""
    import time

    if _SUMMARY_CACHE["data"] is not None and time.monotonic() - _SUMMARY_CACHE["at"] < SUMMARY_TTL_S:
        return _SUMMARY_CACHE["data"]
    data = await _build_summary(session)
    _SUMMARY_CACHE.update(at=time.monotonic(), data=data)
    return data


async def _build_summary(session: AsyncSession) -> dict:
    from sqlalchemy import func

    from app.db.models import EvalResult, JobRun, RiskSnapshot

    facilities = (await session.execute(select(func.count()).select_from(Facility).where(Facility.active.is_(True)))).scalar() or 0
    run = (await session.execute(select(RiskSnapshot.run_id, RiskSnapshot.created_at).order_by(RiskSnapshot.id.desc()).limit(1))).first()
    sev: dict[str, int] = {}
    series = 0
    if run:
        rows = (await session.execute(select(RiskSnapshot.severity, func.count()).where(RiskSnapshot.run_id == run[0])
                                      .group_by(RiskSnapshot.severity))).all()
        sev = {s: n for s, n in rows}
        series = sum(sev.values())
    out: dict = {"facilities": facilities, "series_monitored": series, "severity_counts": sev,
                 "as_of": run[1] if run else None, "data": "synthetic"}
    for kind in ("backtest", "replay"):
        r = (await session.execute(select(EvalResult).where(EvalResult.kind == kind).order_by(EvalResult.id.desc()).limit(1))).scalar_one_or_none()
        if r and kind == "backtest":
            o = r.payload.get("overall", {})
            out["forecast"] = {"wape_improvement_pct": o.get("wape_improvement_pct"), "coverage80": o.get("coverage80_calibrated")}
        if r and kind == "replay":
            out["replay"] = r.payload.get("improvement", {}) | {"days": r.payload.get("days"),
                                                                "alerts_a": r.payload["policy_a"]["alerts"], "alerts_b": r.payload["policy_b"]["alerts"]}
    last = (await session.execute(select(JobRun.finished_at).where(JobRun.status == "ok").order_by(JobRun.started_at.desc()).limit(1))).scalar()
    out["last_cycle"] = last
    out |= await _network_facts(session)
    return out


async def _network_facts(session: AsyncSession) -> dict:
    """Facts the public site and login page render instead of hard-coding them."""
    from sqlalchemy import func

    from app.db.models import ShelfLifeRule
    from app.domain.rules import ABO_RH

    comp = (await session.execute(select(Facility.subtype, func.count()).where(Facility.active.is_(True))
                                  .group_by(Facility.subtype))).all()
    regions = (await session.execute(select(Region).order_by(Region.id))).scalars().all()
    state = next((r for r in regions if r.level == "state"), None)
    rules = (await session.execute(select(ShelfLifeRule))).scalars().all()
    codes = [spec["facility_code"] for spec in DEMO_USERS.values() if spec.get("facility_code")]
    names = dict((await session.execute(select(Facility.code, Facility.name).where(Facility.code.in_(codes)))).all()) if codes else {}
    roles = {}
    for key, spec in DEMO_USERS.items():
        scope = names.get(spec.get("facility_code"), spec.get("facility_code")) if spec.get("facility_code") else (state.name if state else "network")
        roles[key] = {"role": spec["role"], "title": spec["name"], "scope": scope,
                      "scope_kind": "facility" if spec.get("facility_code") else "region"}
    return {
        "network": {
            "by_subtype": {s: n for s, n in comp},
            "region": state.name if state else None,
            "districts": [r.name for r in regions if r.level == "district"],
            "center": [state.lat, state.lng] if state and state.lat is not None else None,
            "blood_groups": len(ABO_RH),
            "components": len(rules) or 4,
        },
        "rules": {r.component: {"shelf_life_h": r.shelf_life_hours, "min_usable_h": r.min_usable_hours,
                                "min_life_on_arrival_h": r.min_life_on_arrival_hours, "max_transit_h": r.max_transit_hours,
                                "storage": r.storage} for r in rules},
        "engine": {"risk_paths": get_settings().risk_paths, "horizon_h": get_settings().risk_horizon_hours},
        "demo_roles": roles,
    }


class DemoLogin(BaseModel):
    user: str


@router.post("/api/auth/demo-login", tags=["auth"])
async def demo_login(body: DemoLogin, session: AsyncSession = Depends(get_session)) -> dict:
    s = get_settings()
    if s.auth_mode not in ("demo", "both"):
        raise HTTPException(403, "demo login disabled")
    spec = DEMO_USERS.get(body.user)
    if spec is None:
        raise HTTPException(404, f"unknown demo user; choose one of {sorted(DEMO_USERS)}")
    fid = rid = None
    if code := spec.get("facility_code"):
        fid = (await session.execute(select(Facility.id).where(Facility.code == code))).scalar()
    if spec.get("region_code"):
        rid = (await session.execute(select(Region.id).where(Region.level == "state"))).scalar()
    p = Principal(uid=f"demo-{body.user}", role=spec["role"], name=spec["name"], facility_id=fid, region_id=rid)
    return {"token": issue_demo_token(p), "user": p.__dict__}


@router.get("/api/auth/me", tags=["auth"])
async def me(p: Principal = Depends(current_user)) -> dict:
    return p.__dict__


@router.get("/api/regions", tags=["registry"])
async def regions(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> list[dict]:
    rows = (await session.execute(select(Region).order_by(Region.id))).scalars().all()
    return [{"id": r.id, "name": r.name, "parent_id": r.parent_id, "level": r.level, "lat": r.lat, "lng": r.lng} for r in rows]


@router.get("/api/facilities", tags=["registry"])
async def facilities(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> list[dict]:
    allowed = await allowed_facilities(session, p)
    rows = (await session.execute(select(Facility).order_by(Facility.code))).scalars().all()
    return [{"id": f.id, "code": f.code, "name": f.name, "type": f.type, "subtype": f.subtype, "region_id": f.region_id,
             "lat": f.lat, "lng": f.lng, "beds": f.beds, "active": f.active, "is_trauma_centre": f.is_trauma_centre,
             "freshness_h": round(freshness_hours(f), 1) if f.last_reported_at else None,
             "in_scope": allowed is None or f.id in allowed} for f in rows]

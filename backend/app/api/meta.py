from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import gemini_client
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

"""Self sign-up onboarding: a new Firebase account (role 'pending') requests a role at a facility;
a regional coordinator (for facilities in their region) or an admin approves it, which writes the
role custom claims to the Firebase account. The user refreshes their ID token to get access."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AccessRequest, Facility, Region
from app.db.session import get_session
from app.deps import current_user, idempotency_key, idempotent
from app.domain.audit import audit
from app.security import PENDING, Principal
from app.services.scope import allowed_facilities, require_role

log = logging.getLogger(__name__)
router = APIRouter(tags=["access"])


class AccessRequestIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    requested_role: Literal["hospital_user", "bank_manager"]
    facility_id: int
    note: str | None = Field(None, max_length=300)


class Decision(BaseModel):
    note: str | None = Field(None, max_length=300)


def set_firebase_claims(uid: str, claims: dict, display_name: str | None = None) -> None:
    """Write role claims to the Firebase account (Admin SDK). Patched in tests."""
    import firebase_admin
    from firebase_admin import auth

    from app.config import get_settings

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": get_settings().firebase_project_id})
    auth.set_custom_user_claims(uid, claims)
    if display_name:
        auth.update_user(uid, display_name=display_name)


def _out(r: AccessRequest, facs: dict[int, Facility]) -> dict:
    f = facs.get(r.facility_id)
    return {"id": r.id, "uid": r.uid, "email": r.email, "name": r.name, "requested_role": r.requested_role,
            "facility_id": r.facility_id, "facility_name": f.name if f else None, "facility_code": f.code if f else None,
            "note": r.note, "status": r.status, "decided_by": r.decided_by, "decision_note": r.decision_note,
            "created_at": r.created_at, "decided_at": r.decided_at}


async def _facs(session: AsyncSession) -> dict[int, Facility]:
    return {f.id: f for f in (await session.execute(select(Facility))).scalars()}


@router.get("/api/public/facilities")
async def public_facilities(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Facility directory for the sign-up form (names and districts only, no inventory)."""
    regions = {r.id: r.name for r in (await session.execute(select(Region))).scalars()}
    rows = (await session.execute(select(Facility).where(Facility.active.is_(True)).order_by(Facility.name))).scalars()
    return [{"id": f.id, "code": f.code, "name": f.name, "type": f.type, "district": regions.get(f.region_id)} for f in rows]


@router.get("/api/access-requests/mine")
async def my_request(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict | None:
    r = (await session.execute(select(AccessRequest).where(AccessRequest.uid == p.uid))).scalar_one_or_none()
    return _out(r, await _facs(session)) if r else None


@router.post("/api/access-requests")
async def create_request(body: AccessRequestIn, key: str = Depends(idempotency_key),
                         session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    if p.role != PENDING:
        raise HTTPException(409, "your account already has access")
    f = await session.get(Facility, body.facility_id)
    if f is None or not f.active:
        raise HTTPException(404, "facility not found")
    if body.requested_role == "bank_manager" and f.type != "blood_bank":
        raise HTTPException(422, "blood bank roles must be requested at a blood bank")

    async def run():
        r = (await session.execute(select(AccessRequest).where(AccessRequest.uid == p.uid))).scalar_one_or_none()
        if r and r.status == "approved":
            raise HTTPException(409, "request already approved - refresh your session")
        if r is None:
            r = AccessRequest(uid=p.uid)
            session.add(r)
        r.email, r.name, r.requested_role, r.facility_id, r.note = p.name if "@" in (p.name or "") else None, body.name, \
            body.requested_role, body.facility_id, body.note
        r.status, r.decided_by, r.decided_at, r.decision_note = "pending", None, None, None
        await session.flush()
        await audit(session, p, "access.request", "access_request", r.id, after={"role": body.requested_role, "facility_id": body.facility_id})
        await session.refresh(r)
        return _out(r, await _facs(session))

    return await idempotent(session, "access-request", p, key, run)


@router.get("/api/access-requests")
async def list_requests(status: str = "pending", session: AsyncSession = Depends(get_session),
                        p: Principal = Depends(current_user)) -> list[dict]:
    require_role(p, "regional_coordinator")
    allowed = await allowed_facilities(session, p)
    q = select(AccessRequest).where(AccessRequest.status.in_(status.split(","))).order_by(AccessRequest.created_at.desc())
    if allowed is not None:
        q = q.where(AccessRequest.facility_id.in_(allowed or {-1}))
    facs = await _facs(session)
    return [_out(r, facs) for r in (await session.execute(q.limit(200))).scalars()]


async def _decide(request_id: int, approve: bool, body: Decision, key: str, session: AsyncSession, p: Principal) -> dict:
    require_role(p, "regional_coordinator")

    async def run():
        r = await session.get(AccessRequest, request_id, with_for_update=True)
        if r is None:
            raise HTTPException(404, "request not found")
        allowed = await allowed_facilities(session, p)
        if allowed is not None and r.facility_id not in allowed:
            raise HTTPException(403, "facility outside your region")
        if r.status != "pending":
            raise HTTPException(409, f"request is already {r.status}")
        if approve:
            try:
                set_firebase_claims(r.uid, {"role": r.requested_role, "facility_id": r.facility_id, "region_id": None}, r.name)
            except Exception as exc:  # noqa: BLE001
                log.warning("could not set firebase claims: %s", exc)
                raise HTTPException(502, "could not update the Firebase account; try again") from exc
        r.status = "approved" if approve else "rejected"
        r.decided_by, r.decided_at, r.decision_note = p.uid, datetime.now(UTC), body.note
        await audit(session, p, f"access.{r.status}", "access_request", r.id,
                    after={"uid": r.uid, "role": r.requested_role, "facility_id": r.facility_id})
        await session.flush()
        return _out(r, await _facs(session))

    return await idempotent(session, f"access-{'approve' if approve else 'reject'}:{request_id}", p, key, run)


@router.post("/api/access-requests/{request_id}/approve")
async def approve(request_id: int, body: Decision = Decision(), key: str = Depends(idempotency_key),
                  session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _decide(request_id, True, body, key, session, p)


@router.post("/api/access-requests/{request_id}/reject")
async def reject(request_id: int, body: Decision = Decision(), key: str = Depends(idempotency_key),
                 session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    return await _decide(request_id, False, body, key, session, p)

"""FastAPI dependencies: DB session, authenticated principal, idempotency, internal-job auth."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import IdempotencyRecord
from app.db.session import get_session
from app.security import Principal, verify_token

SessionDep = Depends(get_session)


async def current_user(authorization: str | None = Header(None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    p = verify_token(authorization.split(" ", 1)[1].strip())
    if p is None:
        raise HTTPException(401, "invalid or expired token")
    return p


UserDep = Depends(current_user)


def idempotency_key(idempotency_key: str | None = Header(None, alias="Idempotency-Key")) -> str:
    if not idempotency_key or not 8 <= len(idempotency_key) <= 100:
        raise HTTPException(422, "Idempotency-Key header (8-100 chars) is required for write requests")
    return idempotency_key


IdemDep = Depends(idempotency_key)


async def idempotent(session: AsyncSession, scope: str, actor: Principal, key: str,
                     fn: Callable[[], Awaitable[object]]) -> object:
    """Run fn once per (scope, actor, key); replay the stored response on retries."""
    rk = f"{scope}:{actor.uid}:{key}"[:160]
    prev = await session.get(IdempotencyRecord, rk)
    if prev is not None:
        return prev.response | {"idempotent_replay": True} if isinstance(prev.response, dict) else prev.response
    result = jsonable_encoder(await fn())
    session.add(IdempotencyRecord(key=rk, status_code=200, response=result if isinstance(result, dict) else {"data": result}))
    await session.commit()
    return result


async def internal_auth(request: Request, authorization: str | None = Header(None),
                        x_internal_token: str | None = Header(None)) -> str:
    """Cloud Scheduler sends a Google-signed OIDC token (verified here, in code, because the service
    is publicly invokable for the demo). Non-GCP schedulers may use a shared X-Internal-Token."""
    s = get_settings()
    if s.internal_token and x_internal_token and x_internal_token == s.internal_token:
        return "token"
    if authorization and authorization.lower().startswith("bearer ") and s.internal_audience:
        from google.auth.transport import requests as grequests
        from google.oauth2 import id_token

        try:
            claims = id_token.verify_oauth2_token(authorization.split(" ", 1)[1], grequests.Request(),
                                                  audience=s.internal_audience)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(401, f"invalid OIDC token: {exc}") from exc
        if s.scheduler_sa_email and claims.get("email") != s.scheduler_sa_email:
            raise HTTPException(403, "unexpected service account")
        return claims.get("email", "oidc")
    if s.env != "prod" and not s.internal_token and not s.internal_audience:
        return "dev-open"
    raise HTTPException(401, "internal endpoint requires OIDC or X-Internal-Token")

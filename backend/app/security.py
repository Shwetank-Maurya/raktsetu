"""Authentication and role-based scoping.

Two token types are accepted (AUTH_MODE=firebase|demo|both):
- Firebase ID tokens (production). Roles come from custom claims: role, facility_id, region_id.
- Demo tokens: HMAC-signed JSON issued by /api/auth/demo-login, so the app works end to end
  without a Firebase project (local dev, CI, judges without accounts).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import asdict, dataclass

from app.config import get_settings

log = logging.getLogger(__name__)

ROLES = ("hospital_user", "bank_manager", "regional_coordinator", "admin")
# A signed-up account that has not been granted a role yet: sees no data, can only request access.
PENDING = "pending"


@dataclass(frozen=True)
class Principal:
    uid: str
    role: str
    name: str = ""
    facility_id: int | None = None
    region_id: int | None = None
    auth: str = "demo"

    @property
    def is_network_role(self) -> bool:
        return self.role in ("regional_coordinator", "admin")


SYSTEM = Principal(uid="system", role="admin", name="System", auth="system")

# Demo identities. facility codes are resolved to ids at login time (see api/auth.py).
DEMO_USERS: dict[str, dict] = {
    "coordinator": {"role": "regional_coordinator", "name": "Regional Coordinator (Delhi)", "region_code": "STATE"},
    "bank": {"role": "bank_manager", "name": "Blood Bank Manager", "facility_code": "BB-01"},
    "hospital": {"role": "hospital_user", "name": "Transfusion Officer", "facility_code": "LH-01"},
    "admin": {"role": "admin", "name": "Platform Admin", "region_code": "STATE"},
}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_demo_token(p: Principal, ttl_s: int = 12 * 3600) -> str:
    body = asdict(p) | {"exp": int(time.time()) + ttl_s}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = hmac.new(get_settings().demo_auth_secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"demo.{payload}.{_b64(sig)}"


def verify_demo_token(token: str) -> Principal | None:
    try:
        prefix, payload, sig = token.split(".")
        if prefix != "demo":
            return None
        expected = hmac.new(get_settings().demo_auth_secret.encode(), payload.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig)):
            return None
        body = json.loads(_unb64(payload))
        if body.pop("exp", 0) < time.time():
            return None
        if body.get("role") not in (*ROLES, PENDING):
            return None
        return Principal(**body)
    except Exception:  # noqa: BLE001 - any malformed token is simply invalid
        return None


_firebase_ready = False


def _init_firebase() -> bool:
    global _firebase_ready
    if _firebase_ready:
        return True
    settings = get_settings()
    if not settings.firebase_project_id:
        return False
    try:
        import firebase_admin

        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        _firebase_ready = True
    except Exception as exc:  # noqa: BLE001
        log.warning("firebase init failed: %s", exc)
    return _firebase_ready


def verify_firebase_token(token: str) -> Principal | None:
    if not _init_firebase():
        return None
    try:
        from firebase_admin import auth

        claims = auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001
        log.info("firebase token rejected: %s", exc)
        return None
    role = claims.get("role")
    if role not in ROLES:
        # Signed up but not yet approved: no data access, may only file an access request.
        return Principal(uid=claims["uid"], role=PENDING, name=claims.get("name") or claims.get("email", ""), auth="firebase")
    return Principal(
        uid=claims["uid"], role=role, name=claims.get("name") or claims.get("email", ""),
        facility_id=claims.get("facility_id"), region_id=claims.get("region_id"), auth="firebase",
    )


def verify_token(token: str) -> Principal | None:
    mode = get_settings().auth_mode
    if token.startswith("demo.") and mode in ("demo", "both"):
        return verify_demo_token(token)
    if mode in ("firebase", "both"):
        return verify_firebase_token(token)
    return None


def hash_phone(phone: str) -> str:
    """Donor phones are stored only as salted hashes (DPDP data minimisation)."""
    digits = "".join(c for c in phone if c.isdigit())[-10:]
    return hashlib.sha256(f"raktsetu:{digits}".encode()).hexdigest()

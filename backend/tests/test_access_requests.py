"""Sign-up onboarding: pending accounts see nothing, request access, coordinator approves -> claims."""

import pytest

from app.api import access
from tests.conftest import COORD, H1, headers, token

pytestmark = pytest.mark.db
PENDING = lambda uid="new-user": token("pending", uid=uid)  # noqa: E731


async def test_pending_user_sees_no_data(client, db):
    me = (await client.get("/api/auth/me", headers=headers(PENDING()))).json()
    assert me["role"] == "pending"
    m = (await client.get("/api/inventory/matrix", headers=headers(PENDING()))).json()
    assert m["facilities"] == []
    assert (await client.post("/api/transfers/plan", json={}, headers=headers(PENDING(), idem=True))).status_code == 403


async def test_full_signup_approval_flow(client, db, monkeypatch):
    calls = []
    monkeypatch.setattr(access, "set_firebase_claims", lambda uid, claims, name=None: calls.append((uid, claims, name)))
    facs = (await client.get("/api/public/facilities")).json()  # no token needed for the sign-up form
    assert {f["code"] for f in facs} == {"H-1", "H-2", "B-1"} and "inventory" not in str(facs)
    r = await client.post("/api/access-requests", json={"name": "Asha Rao", "requested_role": "hospital_user", "facility_id": 1},
                          headers=headers(PENDING(), idem=True))
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert (await client.get("/api/access-requests/mine", headers=headers(PENDING()))).json()["facility_name"] == "Hospital One"
    # hospital users cannot see or approve requests
    assert (await client.get("/api/access-requests", headers=headers(H1()))).status_code == 403
    pending = (await client.get("/api/access-requests", headers=headers(COORD()))).json()
    assert len(pending) == 1
    ok = await client.post(f"/api/access-requests/{pending[0]['id']}/approve", json={}, headers=headers(COORD(), idem=True))
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    assert calls == [("new-user", {"role": "hospital_user", "facility_id": 1, "region_id": None}, "Asha Rao")]


async def test_bank_role_only_at_blood_bank_and_region_scope(client, db, monkeypatch):
    monkeypatch.setattr(access, "set_firebase_claims", lambda *a, **k: None)
    bad = await client.post("/api/access-requests", json={"name": "Ravi K", "requested_role": "bank_manager", "facility_id": 1},
                            headers=headers(PENDING("u2"), idem=True))
    assert bad.status_code == 422
    await client.post("/api/access-requests", json={"name": "Ravi K", "requested_role": "hospital_user", "facility_id": 2},
                      headers=headers(PENDING("u2"), idem=True))
    district_a = token("regional_coordinator", region_id=2)  # facility 2 is in district B
    rid = (await client.get("/api/access-requests", headers=headers(COORD()))).json()[0]["id"]
    r = await client.post(f"/api/access-requests/{rid}/approve", json={}, headers=headers(district_a, idem=True))
    assert r.status_code == 403


async def test_existing_user_cannot_request_again(client, db):
    r = await client.post("/api/access-requests", json={"name": "Someone", "requested_role": "hospital_user", "facility_id": 1},
                          headers=headers(H1(), idem=True))
    assert r.status_code == 409

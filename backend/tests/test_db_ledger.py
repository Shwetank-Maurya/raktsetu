"""Ledger, reservations and data-integrity edge cases (#1, #2, #4, #5, #7, #9, #11, #15) against Postgres."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db.models import BloodUnit, InventoryEvent, RejectedEntry
from app.domain import reservations
from app.domain.compat import RuleBook
from app.domain.errors import InsufficientStock
from app.domain.stock import usable_counts
from app.schemas import ReservationIn
from app.security import Principal
from tests.conftest import BANK, H1, add_units, headers

pytestmark = pytest.mark.db


async def test_duplicate_submissions_create_one_event(client, db):
    h = headers(BANK(), idem=True)
    body = {"type": "receive", "facility_id": 3, "abo_rh": "O-", "component": "RBC", "quantity": 4}
    results = [await client.post("/api/inventory/events", json=body, headers=h) for _ in range(5)]
    assert all(r.status_code == 200 for r in results)
    assert sum(1 for r in results if r.json()["duplicate"]) == 4
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(InventoryEvent))).scalar() == 1
        assert (await s.execute(select(func.count()).select_from(BloodUnit))).scalar() == 4


async def test_concurrent_duplicate_keys_are_safe(client, db):
    h = headers(BANK(), idem=True)
    body = {"type": "receive", "facility_id": 3, "abo_rh": "A+", "component": "RBC", "quantity": 2}
    rs = await asyncio.gather(*[client.post("/api/inventory/events", json=body, headers=h) for _ in range(8)])
    assert all(r.status_code == 200 for r in rs)
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(BloodUnit))).scalar() == 2


async def test_fifty_parallel_reservations_for_ten_units(db):
    async with db() as s:
        add_units(s, 1, "O-", "RBC", 10)
        await s.commit()
    actor = Principal(uid="t", role="hospital_user", facility_id=1)

    async def one():
        async with db() as s:
            try:
                await reservations.reserve(s, actor, ReservationIn(facility_id=1, abo_rh="O-", component="RBC", quantity=1))
                await s.commit()
                return True
            except InsufficientStock:
                await s.rollback()
                return False

    results = await asyncio.gather(*[one() for _ in range(50)])
    assert sum(results) == 10
    async with db() as s:
        assert (await s.execute(select(func.count()).where(BloodUnit.status == "reserved"))).scalar() == 10


async def test_reservation_ttl_releases_units(db):
    async with db() as s:
        add_units(s, 1, "B+", "RBC", 2)
        await s.commit()
    actor = Principal(uid="t", role="hospital_user", facility_id=1)
    async with db() as s:
        r = await reservations.reserve(s, actor, ReservationIn(facility_id=1, abo_rh="B+", component="RBC", quantity=2))
        r.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()
    async with db() as s:
        assert await reservations.release_expired(s) == 1
        await s.commit()
        assert (await usable_counts(s, RuleBook.default()))[(1, "B+", "RBC")] == 2


@pytest.mark.parametrize("body,reason", [
    ({"type": "receive", "facility_id": 3, "abo_rh": "C+", "component": "RBC"}, "abo_rh"),
    ({"type": "issue", "facility_id": 3, "abo_rh": "O+", "component": "RBC", "quantity": -4}, "greater than"),
    ({"type": "receive", "facility_id": 3, "abo_rh": "O+", "component": "RBC",
      "collected_at": "2026-11-20T00:00:00Z", "expires_at": "2026-11-01T00:00:00Z"}, "after collected_at"),
    ({"type": "receive", "facility_id": 3, "abo_rh": "O+", "component": "RBC", "volume_ml": 3500}, "volume_ml"),
    ({"type": "receive", "facility_id": 3, "abo_rh": "O+", "component": "PLT",
      "collected_at": "2026-11-20T00:00:00", "expires_at": "2026-11-29T00:00:00"}, "timezone"),
])
async def test_impossible_values_rejected_and_kept(client, db, body, reason):
    r = await client.post("/api/inventory/events", json=body, headers=headers(BANK(), idem=True))
    assert r.status_code == 422 and reason in r.text
    async with db() as s:
        assert (await s.execute(select(func.count()).select_from(RejectedEntry))).scalar() == 1


async def test_near_expiry_units_not_usable(db):
    async with db() as s:
        add_units(s, 1, "O+", "PLT", 1, life_h=11)  # below 12 h platelet minimum
        add_units(s, 1, "O+", "PLT", 1, life_h=13)
        await s.commit()
        assert (await usable_counts(s, RuleBook.default()))[(1, "O+", "PLT")] == 1


async def test_quarantined_and_reserved_excluded_and_recall_blocks_siblings(client, db):
    async with db() as s:
        add_units(s, 1, "A+", "RBC", 1, donation="DX1")
        add_units(s, 3, "A+", "FFP", 1, donation="DX1-2")  # sibling component at another facility
        add_units(s, 1, "A+", "RBC", 2, status="reserved")
        await s.commit()
    r = await client.post("/api/inventory/events", json={"type": "recall", "facility_id": 1, "donation_id": "DX1"},
                          headers=headers(H1(), idem=True))
    assert r.status_code == 200 and r.json()["count"] == 2 and r.json()["facilities"] == [1, 3]
    async with db() as s:
        u = await usable_counts(s, RuleBook.default())
        assert u.get((1, "A+", "RBC"), 0) == 0 and u.get((3, "A+", "FFP"), 0) == 0


async def test_issue_is_fefo_and_updates_consumption(client, db):
    async with db() as s:
        early = add_units(s, 1, "O+", "RBC", 1, life_h=100)[0]
        add_units(s, 1, "O+", "RBC", 1, life_h=600)
        await s.commit()
    r = await client.post("/api/inventory/events", json={"type": "issue", "facility_id": 1, "abo_rh": "O+",
                                                         "component": "RBC", "quantity": 1, "emergency": True},
                          headers=headers(H1(), idem=True))
    assert r.json()["unit_ids"] == [early.id]


async def test_backdated_event_keeps_event_and_ingest_time(client, db):
    t = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    r = await client.post("/api/inventory/events", json={"type": "receive", "facility_id": 3, "abo_rh": "O+",
                                                         "component": "RBC", "event_time": t},
                          headers=headers(BANK(), idem=True))
    async with db() as s:
        ev = await s.get(InventoryEvent, r.json()["event_id"])
        assert ev.ingest_time - ev.event_time > timedelta(days=1)


async def test_cannot_write_to_other_facility(client, db):
    r = await client.post("/api/inventory/events", json={"type": "receive", "facility_id": 2, "abo_rh": "O+",
                                                         "component": "RBC"}, headers=headers(H1(), idem=True))
    assert r.status_code == 403


async def test_write_requires_idempotency_key(client, db):
    r = await client.post("/api/inventory/events", json={"type": "receive", "facility_id": 1, "abo_rh": "O+",
                                                         "component": "RBC"}, headers=headers(H1()))
    assert r.status_code == 422

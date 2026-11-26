"""Test fixtures. DB tests use a separate database (TEST_DATABASE_URL, default raktsetu_test on the
local Docker Postgres). CI provides a Postgres service container or a Neon branch."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault("TEST_DATABASE_URL", "postgresql://raktsetu:raktsetu@localhost:55432/raktsetu_test")
TEST_URL = os.environ["TEST_DATABASE_URL"]
os.environ["DATABASE_URL"] = TEST_URL
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
os.environ["MAPS_SERVER_KEY"] = ""
os.environ["FIRESTORE_ENABLED"] = "false"
os.environ["ENV"] = "test"
os.environ["RISK_PATHS"] = "400"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db.models import Base, BloodUnit, Facility, Region  # noqa: E402
from app.db.session import get_sessionmaker, make_engine, set_engine  # noqa: E402
from app.domain.compat import seed_rules  # noqa: E402
from app.security import Principal, issue_demo_token  # noqa: E402


def _ensure_db() -> bool:
    base, name = TEST_URL.rsplit("/", 1)
    try:
        conn = psycopg2.connect(base + "/postgres", connect_timeout=3)
    except Exception:  # noqa: BLE001
        return False
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
    if not cur.fetchone():
        cur.execute(f'CREATE DATABASE "{name}"')
    conn.close()
    return True


DB_AVAILABLE = _ensure_db()


@pytest.fixture(scope="session")
async def engine():
    if not DB_AVAILABLE:
        pytest.skip("test database not reachable")
    eng = make_engine(get_settings().async_database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    set_engine(eng)
    yield eng
    await eng.dispose()


TABLES = ["audit_log", "idempotency_records", "inventory_events", "rejected_entries", "risk_snapshots",
          "demand_forecasts", "alerts", "reservations", "transfer_requests", "blood_units", "consumption_daily",
          "scheduled_demand", "donors", "calendar_events", "job_runs", "job_locks", "eval_results", "app_config",
          "compat_rules", "shelf_life_rules", "facilities", "regions"]


@pytest.fixture
async def db(engine):
    """Fresh minimal network per test: state + 2 districts, 2 hospitals, 1 blood bank."""
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    sm = get_sessionmaker()
    async with sm() as s:
        s.add_all([
            Region(id=1, name="State", level="state", lat=28.6, lng=77.2),
            Region(id=2, name="District A", parent_id=1, level="district"),
            Region(id=3, name="District B", parent_id=1, level="district"),
        ])
        await s.flush()
        now = datetime.now(UTC)
        s.add_all([
            Facility(id=1, code="H-1", name="Hospital One", type="hospital", subtype="large", region_id=2,
                     lat=28.60, lng=77.20, beds=500, last_reported_at=now),
            Facility(id=2, code="H-2", name="Hospital Two", type="hospital", subtype="small", region_id=3,
                     lat=28.65, lng=77.25, beds=60, last_reported_at=now),
            Facility(id=3, code="B-1", name="Blood Bank One", type="blood_bank", subtype="bank", region_id=2,
                     lat=28.62, lng=77.22, last_reported_at=now),
        ])
        await seed_rules(s)
        await s.commit()
    yield sm


def add_units(session, facility_id: int, abo_rh: str, component: str, n: int, life_h: float = 500.0,
              status: str = "available", donation: str | None = None) -> list[BloodUnit]:
    now = datetime.now(UTC)
    shelf = {"RBC": 1008, "PLT": 120, "FFP": 8760, "CRYO": 8760}[component]
    units = [BloodUnit(id=str(uuid.uuid4()), donation_id=donation or f"D{uuid.uuid4().hex[:8]}", facility_id=facility_id,
                       abo_rh=abo_rh, component=component, collected_at=now + timedelta(hours=life_h - shelf),
                       expires_at=now + timedelta(hours=life_h), volume_ml=280 if component == "RBC" else 60,
                       status=status) for _ in range(n)]
    session.add_all(units)
    return units


def token(role: str, facility_id: int | None = None, region_id: int | None = None, uid: str | None = None) -> str:
    return issue_demo_token(Principal(uid=uid or f"t-{role}-{facility_id}", role=role, facility_id=facility_id,
                                      region_id=region_id))


def headers(tok: str, idem: bool = False) -> dict:
    h = {"authorization": f"Bearer {tok}"}
    if idem:
        h["Idempotency-Key"] = uuid.uuid4().hex
    return h


@pytest.fixture
async def client(db):
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


COORD = lambda: token("regional_coordinator", region_id=1)  # noqa: E731
H1 = lambda: token("hospital_user", facility_id=1)  # noqa: E731
H2 = lambda: token("hospital_user", facility_id=2)  # noqa: E731
BANK = lambda: token("bank_manager", facility_id=3)  # noqa: E731

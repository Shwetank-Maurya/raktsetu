"""The hourly cycle called by Cloud Scheduler: housekeeping -> forecast (daily) -> risk -> plan ->
alerts -> live mirror -> analytics export. Guarded by a lease lock so overlapping runs on
multiple Cloud Run instances cannot double-alert (edge case #38)."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Facility, JobLock, JobRun
from app.db.session import get_sessionmaker
from app.domain import ledger, reservations, transfers
from app.domain.compat import load_rulebook
from app.domain.ledger import now_utc
from app.domain.stock import freshness_hours, status_counts
from app.services import alerts, realtime
from app.services.forecasting import forecasts_are_current, run_forecasts, today_ist
from app.services.planning import build_plan, persist_plan
from app.services.risk import STALE_HOURS, compute_risk

log = logging.getLogger(__name__)
LOCK_TTL = timedelta(minutes=20)


async def acquire_lock(session: AsyncSession, name: str, holder: str) -> bool:
    now = now_utc()
    stmt = (pg_insert(JobLock).values(name=name, holder=holder, expires_at=now + LOCK_TTL)
            .on_conflict_do_update(index_elements=["name"], set_={"holder": holder, "expires_at": now + LOCK_TTL},
                                   where=JobLock.expires_at < now)
            .returning(JobLock.holder))
    got = (await session.execute(stmt)).scalar_one_or_none()
    await session.commit()
    return got == holder


async def release_lock(session: AsyncSession, name: str, holder: str) -> None:
    await session.execute(text("DELETE FROM job_locks WHERE name = :n AND holder = :h"), {"n": name, "h": holder})
    await session.commit()


async def close_day(session: AsyncSession) -> int:
    """Write explicit zero rows for yesterday for every facility that reported that day, so
    'no issues' is recorded as zero while silent facilities stay missing (edge case #22)."""
    day = today_ist() - timedelta(days=1)
    res = await session.execute(text("""
        INSERT INTO consumption_daily (facility_id, date, abo_rh, component, units_issued, units_emergency,
                                       units_scheduled, is_event_day, data_quality)
        SELECT f.id, :d, g.g, c.c, 0, 0, 0, false, 'ok'
        FROM facilities f
        CROSS JOIN (VALUES ('O-'),('O+'),('A-'),('A+'),('B-'),('B+'),('AB-'),('AB+')) AS g(g)
        CROSS JOIN (VALUES ('RBC'),('PLT'),('FFP'),('CRYO')) AS c(c)
        WHERE f.active AND f.last_reported_at >= CAST(:d AS date) - interval '5 hours 30 minutes'
        ON CONFLICT DO NOTHING
    """), {"d": day})
    return res.rowcount or 0


async def stock_summaries(session: AsyncSession, risk_rows: list[dict]) -> list[dict]:
    facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    counts = await status_counts(session)
    worst: dict[int, str] = {}
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    for r in risk_rows:
        if order[r["severity"]] > order.get(worst.get(r["facility_id"], "low"), 0):
            worst[r["facility_id"]] = r["severity"]
    out = []
    for fid, f in facs.items():
        avail = {f"{g}|{c}": v.get("available", 0) for (ff, g, c), v in counts.items() if ff == fid}
        out.append({"facility_id": fid, "region_id": f.region_id, "name": f.name, "worst_severity": worst.get(fid, "low"),
                    "available_total": sum(avail.values()), "available": avail,
                    "freshness_h": freshness_hours(f)})
    return out


async def run_cycle(force_forecast: bool = False, trigger: str = "scheduler") -> dict:
    holder = str(uuid.uuid4())
    sm = get_sessionmaker()
    async with sm() as session:
        if not await acquire_lock(session, "run-cycle", holder):
            return {"skipped": True, "reason": "another cycle is running"}
    t0 = time.perf_counter()
    stats: dict = {"trigger": trigger}
    try:
        async with sm() as session:
            run = JobRun(kind="run-cycle")
            session.add(run)
            stats["expired_units"] = await ledger.sweep_expired(session)
            stats["released_reservations"] = await reservations.release_expired(session)
            stats["expired_approvals"] = await transfers.expire_stale_approvals(session)
            stats["closed_day_rows"] = await close_day(session)
            await session.commit()

            if force_forecast or not await forecasts_are_current(session):
                tf = time.perf_counter()
                stats["forecast"] = await run_forecasts(session)
                stats["forecast_s"] = round(time.perf_counter() - tf, 1)
                await session.commit()

            book = await load_rulebook(session)
            tr = time.perf_counter()
            risk_rows = await compute_risk(session, book)
            stats["risk_series"] = len(risk_rows)
            stats["risk_s"] = round(time.perf_counter() - tr, 1)
            stats["severity_counts"] = {s: sum(1 for r in risk_rows if r["severity"] == s)
                                        for s in ("critical", "high", "medium", "low")}
            await session.commit()

            result, fmap = await build_plan(session, book, risk_rows)
            await persist_plan(session, result)
            stats["plan"] = result.stats
            await session.commit()

            facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
            stale = {fid: (freshness_hours(f) or 999.0) for fid, f in facs.items()
                     if f.active and (freshness_hours(f) or 999.0) > STALE_HOURS}
            cands = (alerts.candidates_from_risk(risk_rows, facs) + alerts.stale_candidates(facs, stale)
                     + alerts.deficit_candidates(result.deficits, facs))
            stats["alerts"] = await alerts.evaluate(
                session, cands, {"stockout_risk", "near_expiry", "data_silent", "regional_deficit"})
            await session.commit()

            realtime.mirror_stock_summaries(await stock_summaries(session, risk_rows))
            realtime.mirror_event("cycle", {"run_id": run.id})
            try:
                from app.services.analytics import export_snapshot

                stats["bigquery"] = await export_snapshot(session, risk_rows)
            except Exception as exc:  # noqa: BLE001
                stats["bigquery"] = f"skipped: {exc}"
            stats["duration_s"] = round(time.perf_counter() - t0, 1)
            run.status, run.stats, run.finished_at = "ok", stats, now_utc()
            await session.commit()
            return stats
    except Exception as exc:
        log.exception("cycle failed")
        async with sm() as session:
            session.add(JobRun(kind="run-cycle", status="failed", stats={"error": str(exc)[:500]}, finished_at=now_utc()))
            await session.commit()
        raise
    finally:
        async with sm() as session:
            await release_lock(session, "run-cycle", holder)

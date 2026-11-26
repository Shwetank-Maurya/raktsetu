"""Builds risk inputs from live stock + forecasts and runs the Monte Carlo engine for every series."""

from __future__ import annotations

import logging
import uuid
import zlib
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import CalendarEvent, ConsumptionDaily, Facility, RiskSnapshot, TransferRequest
from app.domain.compat import RuleBook
from app.domain.ledger import IST, now_utc
from app.domain.stock import expiry_profiles, freshness_hours
from app.ml.risk_sim import RiskInput, confidence, rule_based, simulate
from app.optimizer.routes import fallback_eta
from app.services.forecasting import history_meta, latest_forecasts, today_ist

log = logging.getLogger(__name__)
STALE_HOURS = 12.0


async def lead_times(session: AsyncSession) -> dict[int, float]:
    """Hours for the fastest plausible resupply: ETA from the nearest blood bank + 1 h preparation."""
    facs = (await session.execute(select(Facility).where(Facility.active.is_(True)))).scalars().all()
    banks = [f for f in facs if f.type == "blood_bank"]
    out = {}
    for f in facs:
        cands = [fallback_eta((f.lat, f.lng), (b.lat, b.lng))[0] for b in banks if b.id != f.id]
        out[f.id] = (min(cands) if cands else 60.0) / 60 + 1.0
    return out


async def incoming_by_series(session: AsyncSession, book: RuleBook) -> dict[tuple[int, str, str], list[tuple[float, float]]]:
    """Approved/dispatched transfers count as future supply at the destination."""
    now = now_utc()
    rows = (await session.execute(
        select(TransferRequest).where(TransferRequest.status.in_(("approved", "dispatched")))
    )).scalars().all()
    out: dict[tuple[int, str, str], list[tuple[float, float]]] = {}
    for t in rows:
        start = t.dispatched_at or now
        arrival = max(0.0, (start - now).total_seconds() / 3600 + t.eta_minutes / 60)
        life = max(1.0, t.min_life_on_arrival_h - book.shelf[t.component].min_usable_hours)
        out.setdefault((t.to_facility_id, t.abo_rh, t.component), []).extend([(arrival, life)] * t.quantity)
    return out


async def event_multipliers(session: AsyncSession, forecasts: dict) -> dict[int, float]:
    """Anomaly detection (edge case #18): today's issues vs the expected share of today's median.
    A facility far above expectation switches to event mode and its demand is inflated."""
    now_ist = datetime.now(IST)
    frac = max(0.15, (now_ist.hour + now_ist.minute / 60) / 24)
    today = today_ist()
    rows = (await session.execute(
        select(ConsumptionDaily.facility_id, func.sum(ConsumptionDaily.units_issued))
        .where(ConsumptionDaily.date == today).group_by(ConsumptionDaily.facility_id)
    )).all()
    actual = {f: float(n) for f, n in rows}
    expected: dict[int, float] = {}
    spread: dict[int, float] = {}
    for (fid, _, _), fc in forecasts.items():
        if fc:
            expected[fid] = expected.get(fid, 0) + fc[0].q50 + fc[0].scheduled_units
            spread[fid] = spread.get(fid, 0) + max(fc[0].q90 - fc[0].q50, 0.5)
    out: dict[int, float] = {}
    for fid, a in actual.items():
        e = expected.get(fid, 0) * frac
        z = (a - e) / (spread.get(fid, 1.0) * max(frac, 0.3) ** 0.5 + 1e-6)
        if a >= 4 and z > 3:
            out[fid] = round(min(3.0, a / (e + 0.5)), 2)
    # Manually injected incidents (calendar_events kind=incident today) also trigger event mode.
    inc = (await session.execute(select(CalendarEvent).where(CalendarEvent.kind == "incident",
                                                             CalendarEvent.date == today))).scalars().all()
    if inc:
        facs = (await session.execute(select(Facility.id, Facility.region_id))).all()
        for e in inc:
            for fid, rid in facs:
                if e.region_id in (None, rid):
                    out[fid] = max(out.get(fid, 1.0), 1 + e.weight)
    return out


async def previous_severity(session: AsyncSession) -> dict[tuple[int, str, str], str]:
    sub = (select(RiskSnapshot.facility_id, RiskSnapshot.abo_rh, RiskSnapshot.component,
                  func.max(RiskSnapshot.id).label("mid"))
           .group_by(RiskSnapshot.facility_id, RiskSnapshot.abo_rh, RiskSnapshot.component).subquery())
    rows = (await session.execute(select(RiskSnapshot).join(sub, RiskSnapshot.id == sub.c.mid))).scalars().all()
    return {(r.facility_id, r.abo_rh, r.component): r.severity for r in rows}


async def compute_risk(
    session: AsyncSession, book: RuleBook, persist: bool = True,
    extra_demand: dict[tuple[int, str, str], list[float]] | None = None,
    facility_ids: set[int] | None = None, n_paths: int | None = None,
) -> list[dict]:
    """Returns one dict per series. extra_demand adds deterministic units per day (incident what-if)."""
    settings = get_settings()
    n_paths = n_paths or settings.risk_paths
    run_id = str(uuid.uuid4())
    facs = {f.id: f for f in (await session.execute(select(Facility).where(Facility.active.is_(True)))).scalars()}
    if facility_ids is not None:
        facs = {k: v for k, v in facs.items() if k in facility_ids}
    forecasts = await latest_forecasts(session, set(facs))
    profiles = await expiry_profiles(session, book, set(facs))
    incoming = await incoming_by_series(session, book)
    prev = await previous_severity(session)
    leads = await lead_times(session)
    events = await event_multipliers(session, forecasts)
    meta = await history_meta(session)
    now = now_utc()
    start_hour = datetime.now(IST).hour
    trailing = await _trailing_mean(session, set(facs))

    keys = set(forecasts) | set(profiles) | set(extra_demand or {})
    out = []
    for key in sorted(keys):
        fid, g, c = key
        f = facs.get(fid)
        if f is None:
            continue
        fc = forecasts.get(key, [])
        units = list(profiles.get(key, []))
        fresh = freshness_hours(f, now)
        stale = fresh is None or fresh > STALE_HOURS
        lead = leads.get(fid, 2.0)
        mult = events.get(fid, 1.0)
        extra = (extra_demand or {}).get(key, [])
        model_used = fc[0].model_name if fc else "rule_based"
        if fc:
            q10 = [r.q10 for r in fc[:7]]
            q50 = [r.q50 for r in fc[:7]]
            q90 = [r.q90 for r in fc[:7]]
            mu = [r.mean if r.mean is not None else r.q50 for r in fc[:7]]
            sched = [r.scheduled_units + (extra[i] if i < len(extra) else 0) for i, r in enumerate(fc[:7])]
            if stale and fresh is not None:
                # Pessimistic assumption: stock has been consumed since the last report.
                drop = int(round(q50[0] * min(fresh, 72) / 24))
                units = units[drop:]
            if not q50 or (max(q50) == 0 and not units and not any(sched)):
                continue
            seed = zlib.crc32(f"{fid}:{g}:{c}".encode())
            res = simulate(RiskInput(units, q10, q50, q90, sched, incoming.get(key, []), lead, mult, start_hour, mu),
                           n_paths=n_paths, horizon_h=settings.risk_horizon_hours, seed=seed,
                           previous_severity=prev.get(key))
            m = meta.get(f"{fid}:{g}:{c}", {})
            conf = confidence(fresh, q10[0], q50[0], q90[0], int(m.get("history_days", 60)), float(m.get("agreement", 0.8)))
        else:
            tm = trailing.get(key, 0.0) * mult + (sum(extra[:3]) / 3 if extra else 0)
            if tm == 0 and not units:
                continue
            res = rule_based(len(units), tm, lead)
            conf = 0.3
            q50 = [tm]
        row = {
            "facility_id": fid, "abo_rh": g, "component": c, "usable_units": res.usable_units,
            "p_stockout_24": res.p_stockout_24, "p_stockout_48": res.p_stockout_48, "p_stockout_72": res.p_stockout_72,
            "p_stockout_lead": res.p_stockout_lead, "tts_p10": res.tts_p10, "tts_p50": res.tts_p50,
            "days_cover": res.days_cover, "expected_wastage": res.expected_wastage, "risk_score": res.risk_score,
            "severity": res.severity, "confidence": conf, "stale": stale, "lead_time_h": round(lead, 2),
            "model_used": model_used, "event_mode": mult > 1.0, "mean_daily_demand": res.mean_daily_demand,
            # Expected (mean) daily demand incl. scheduled units - what the optimizer plans against.
            "daily_q50": res.mean_daily_demand,
            "daily_q90": max(float(fc[0].q90) if fc else res.mean_daily_demand * 1.5, res.mean_daily_demand),
            "freshness_h": round(fresh, 1) if fresh is not None else None,
        }
        out.append(row)
    if persist:
        session.add_all([RiskSnapshot(run_id=run_id, **{k: v for k, v in r.items() if k in _SNAP_COLS}) for r in out])
        await session.execute(delete(RiskSnapshot).where(RiskSnapshot.created_at < now - timedelta(days=3)))
        await session.flush()
    return out


_SNAP_COLS = {c.name for c in RiskSnapshot.__table__.columns} - {"id", "run_id", "created_at"}


async def _trailing_mean(session: AsyncSession, fids: set[int]) -> dict[tuple[int, str, str], float]:
    start = today_ist() - timedelta(days=14)
    rows = (await session.execute(
        select(ConsumptionDaily.facility_id, ConsumptionDaily.abo_rh, ConsumptionDaily.component,
               func.sum(ConsumptionDaily.units_issued))
        .where(ConsumptionDaily.date >= start, ConsumptionDaily.facility_id.in_(fids))
        .group_by(ConsumptionDaily.facility_id, ConsumptionDaily.abo_rh, ConsumptionDaily.component)
    )).all()
    return {(f, g, c): float(n) / 14 for f, g, c, n in rows}


async def latest_risk(session: AsyncSession, facility_ids: set[int] | None = None) -> list[RiskSnapshot]:
    run = (await session.execute(select(RiskSnapshot.run_id).order_by(RiskSnapshot.id.desc()).limit(1))).scalar()
    if run is None:
        return []
    q = select(RiskSnapshot).where(RiskSnapshot.run_id == run)
    if facility_ids is not None:
        q = q.where(RiskSnapshot.facility_id.in_(facility_ids))
    return list((await session.execute(q)).scalars().all())

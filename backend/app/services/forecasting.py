"""Loads history into a Panel, runs the daily forecast pipeline and persists results."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CalendarEvent, ConsumptionDaily, DemandForecast, EvalResult, Facility, ScheduledDemand
from app.domain.ledger import IST
from app.domain.rules import ABO_RH, COMPONENTS
from app.ml.calendar import static_festivals
from app.ml.forecast import HORIZON, MODEL_VERSION, Panel, forecast_all

log = logging.getLogger(__name__)


def today_ist() -> date:
    return datetime.now(IST).date()


async def festivals_from_db(session: AsyncSession) -> dict:
    fest = static_festivals()
    rows = (await session.execute(select(CalendarEvent).where(CalendarEvent.kind.in_(("festival", "holiday"))))).scalars()
    for r in rows:
        fest[r.date] = (r.name, r.weight)
    return fest


async def load_panel(session: AsyncSession, days: int = 365, end: date | None = None) -> Panel:
    end = end or today_ist()  # panel covers [end - days, end - 1]
    start = end - timedelta(days=days)
    facs = (await session.execute(select(Facility).where(Facility.active.is_(True)).order_by(Facility.id))).scalars().all()
    keys = [(f.id, g, c) for f in facs for g in ABO_RH for c in COMPONENTS]
    index = {k: i for i, k in enumerate(keys)}
    y = np.full((len(keys), days), np.nan)
    ev = np.zeros((len(keys), days), dtype=bool)
    rows = await session.execute(
        select(ConsumptionDaily.facility_id, ConsumptionDaily.abo_rh, ConsumptionDaily.component, ConsumptionDaily.date,
               ConsumptionDaily.units_issued, ConsumptionDaily.units_scheduled, ConsumptionDaily.is_event_day)
        .where(ConsumptionDaily.date >= start, ConsumptionDaily.date < end)
    )
    for fid, g, c, d, issued, sched, is_ev in rows.all():
        s = index.get((fid, g, c))
        if s is None:
            continue
        di = (d - start).days
        y[s, di] = max(0, issued - sched)
        ev[s, di] = is_ev
    sched_arr = np.zeros((len(keys), days + HORIZON + 1))
    srows = await session.execute(
        select(ScheduledDemand.facility_id, ScheduledDemand.abo_rh, ScheduledDemand.component,
               ScheduledDemand.due_date, func.sum(ScheduledDemand.units))
        .where(ScheduledDemand.due_date >= start, ScheduledDemand.due_date <= end + timedelta(days=HORIZON))
        .group_by(ScheduledDemand.facility_id, ScheduledDemand.abo_rh, ScheduledDemand.component, ScheduledDemand.due_date)
    )
    for fid, g, c, d, u in srows.all():
        s = index.get((fid, g, c))
        if s is not None:
            sched_arr[s, (d - start).days] = float(u)
    attrs = {f.id: {"type": f.type, "subtype": f.subtype, "beds": f.beds, "is_trauma_centre": f.is_trauma_centre}
             for f in facs}
    return Panel(start, keys, y, ev, sched_arr, attrs, await festivals_from_db(session))


async def run_forecasts(session: AsyncSession) -> dict:
    run_id = str(uuid.uuid4())
    panel = await load_panel(session)
    forecasts, report = forecast_all(panel)
    origin_day = panel.day(panel.n_days - 1)
    rows = []
    for fc in forecasts:
        fid, g, c = fc.key
        for h in range(HORIZON):
            rows.append(DemandForecast(
                run_id=run_id, facility_id=fid, abo_rh=g, component=c, target_date=origin_day + timedelta(days=h + 1),
                q10=fc.q10[h], q50=fc.q50[h], q90=fc.q90[h], mean=fc.mean[h] if fc.mean else None, scheduled_units=fc.scheduled[h],
                model_name=fc.model, model_version=MODEL_VERSION,
                drivers=fc.drivers if h == 0 else None,
            ))
    await session.execute(delete(DemandForecast))  # keep only the latest run (free-tier storage)
    session.add_all(rows)
    session.add(EvalResult(kind="backtest", payload={
        "run_id": run_id, "overall": report.overall, "metrics": report.metrics, "chosen": report.chosen,
        "conformal": report.conformal, "history_meta": {
            f"{k[0]}:{k[1]}:{k[2]}": {"history_days": f.history_days, "agreement": f.agreement}
            for k, f in ((f.key, f) for f in forecasts)},
    }))
    await session.flush()
    return {"run_id": run_id, "series": len(forecasts), "overall": report.overall}


async def latest_forecasts(session: AsyncSession, facility_ids: set[int] | None = None) -> dict[tuple[int, str, str], list[DemandForecast]]:
    q = select(DemandForecast).order_by(DemandForecast.target_date)
    if facility_ids is not None:
        q = q.where(DemandForecast.facility_id.in_(facility_ids))
    out: dict[tuple[int, str, str], list[DemandForecast]] = {}
    for r in (await session.execute(q)).scalars().all():
        out.setdefault((r.facility_id, r.abo_rh, r.component), []).append(r)
    return out


async def forecasts_are_current(session: AsyncSession) -> bool:
    latest = (await session.execute(select(func.max(DemandForecast.created_at)))).scalar()
    if latest is None:
        return False
    return latest.astimezone(IST).date() == today_ist()


async def history_meta(session: AsyncSession) -> dict[str, dict]:
    row = (await session.execute(
        select(EvalResult).where(EvalResult.kind == "backtest").order_by(EvalResult.id.desc()).limit(1)
    )).scalar_one_or_none()
    return (row.payload or {}).get("history_meta", {}) if row else {}

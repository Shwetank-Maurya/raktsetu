from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, ConsumptionDaily, DemandForecast, Facility, TransferRequest
from app.db.session import get_session
from app.deps import current_user
from app.domain.compat import load_rulebook
from app.domain.ledger import now_utc
from app.domain.rules import SEVERITY_ORDER
from app.domain.stock import freshness_hours
from app.security import Principal
from app.services import availability
from app.services.forecasting import today_ist
from app.services.risk import latest_risk
from app.services.scope import allowed_facilities, assert_facility

router = APIRouter(prefix="/api", tags=["risk"])


def _risk_dict(r, f: Facility) -> dict:
    return {"facility_id": r.facility_id, "facility_name": f.name, "facility_code": f.code, "region_id": f.region_id,
            "abo_rh": r.abo_rh, "component": r.component, "usable_units": r.usable_units,
            "p_stockout_24": r.p_stockout_24, "p_stockout_48": r.p_stockout_48, "p_stockout_72": r.p_stockout_72,
            "tts_p10": r.tts_p10, "tts_p50": r.tts_p50, "days_cover": r.days_cover,
            "expected_wastage": r.expected_wastage, "risk_score": r.risk_score, "severity": r.severity,
            "confidence": r.confidence, "stale": r.stale, "lead_time_h": r.lead_time_h, "model_used": r.model_used,
            "event_mode": r.event_mode, "as_of": r.created_at}


@router.get("/risk")
async def risk(region_id: int | None = None, severity: str | None = None, facility_id: int | None = None,
               limit: int = Query(200, le=2000), session: AsyncSession = Depends(get_session),
               p: Principal = Depends(current_user)) -> dict:
    allowed = await allowed_facilities(session, p)
    facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    rows = await latest_risk(session, allowed)
    out = [_risk_dict(r, facs[r.facility_id]) for r in rows
           if (region_id is None or facs[r.facility_id].region_id == region_id)
           and (severity is None or r.severity == severity) and (facility_id is None or r.facility_id == facility_id)]
    out.sort(key=lambda x: (-SEVERITY_ORDER[x["severity"]], -x["risk_score"]))
    return {"as_of": out[0]["as_of"] if out else None, "count": len(out), "items": out[:limit]}


@router.get("/kpis")
async def kpis(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    """Command Centre numbers."""
    allowed = await allowed_facilities(session, p)
    rows = await latest_risk(session, allowed)
    facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    scope = [f for f in facs.values() if f.active and (allowed is None or f.id in allowed)]
    sev = {s: sum(1 for r in rows if r.severity == s) for s in ("critical", "high", "medium", "low")}
    alerts_q = select(func.count()).select_from(Alert).where(Alert.status == "open")
    if allowed is not None:
        alerts_q = alerts_q.where(Alert.facility_id.in_(allowed or {-1}))
    open_alerts = (await session.execute(alerts_q)).scalar() or 0
    rescued = (await session.execute(
        select(func.coalesce(func.sum(TransferRequest.quantity), 0))
        .where(TransferRequest.status.in_(("approved", "dispatched", "received")), TransferRequest.kind == "rescue")
    )).scalar() or 0
    pending = (await session.execute(select(func.count()).select_from(TransferRequest)
                                     .where(TransferRequest.status == "proposed"))).scalar() or 0
    # Regional resilience: share of (facility, group) RBC series with >= 2 days cover and not high/critical.
    rbc = [r for r in rows if r.component == "RBC"]
    resilient = sum(1 for r in rbc if r.days_cover >= 2 and SEVERITY_ORDER[r.severity] < 2)
    by_region: dict[int, list] = {}
    for r in rbc:
        by_region.setdefault(facs[r.facility_id].region_id, []).append(r)
    critical = sorted([r for r in rows if r.severity == "critical"], key=lambda r: (r.tts_p50 or 1e9))[:8]
    stale = [f for f in scope if (freshness_hours(f) or 999) > 12]
    return {
        "as_of": rows[0].created_at if rows else None,
        "facilities": len(scope), "severity_counts": sev, "open_alerts": open_alerts, "pending_proposals": pending,
        "wastage_avoided_units": int(rescued),
        "expected_wastage_units": round(sum(r.expected_wastage for r in rows), 1),
        "resilience_score": round(100 * resilient / len(rbc), 1) if rbc else None,
        "regional_resilience": {rid: round(100 * sum(1 for r in rs if r.days_cover >= 2 and SEVERITY_ORDER[r.severity] < 2) / len(rs), 1)
                                for rid, rs in by_region.items()},
        "stale_facilities": [{"id": f.id, "name": f.name, "hours": round(freshness_hours(f) or 999, 1)} for f in stale],
        "critical_countdowns": [_risk_dict(r, facs[r.facility_id]) for r in critical],
    }


@router.get("/map/risk")
async def map_risk(session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    """GeoJSON facility markers coloured by worst severity."""
    allowed = await allowed_facilities(session, p)
    rows = await latest_risk(session, allowed)
    facs = (await session.execute(select(Facility).where(Facility.active.is_(True)))).scalars().all()
    worst: dict[int, object] = {}
    for r in rows:
        cur = worst.get(r.facility_id)
        if cur is None or (SEVERITY_ORDER[r.severity], r.risk_score) > (SEVERITY_ORDER[cur.severity], cur.risk_score):
            worst[r.facility_id] = r
    feats = []
    for f in facs:
        if allowed is not None and f.id not in allowed:
            continue
        w = worst.get(f.id)
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [f.lng, f.lat]}, "properties": {
            "id": f.id, "code": f.code, "name": f.name, "type": f.type, "subtype": f.subtype, "region_id": f.region_id,
            "severity": w.severity if w else "low", "risk_score": w.risk_score if w else 0,
            "worst_series": f"{w.abo_rh} {w.component}" if w else None, "tts_p50": w.tts_p50 if w else None,
            "p_stockout_24": w.p_stockout_24 if w else 0,
            "freshness_h": round(freshness_hours(f), 1) if f.last_reported_at else None}})
    return {"type": "FeatureCollection", "features": feats}


@router.get("/map/heat")
async def map_heat(component: str | None = None, session: AsyncSession = Depends(get_session),
                   p: Principal = Depends(current_user)) -> dict:
    """Weighted points for the deck.gl HeatmapLayer: weight = summed risk score."""
    allowed = await allowed_facilities(session, p)
    rows = await latest_risk(session, allowed)
    facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    agg: dict[int, float] = {}
    for r in rows:
        if component and r.component != component:
            continue
        agg[r.facility_id] = agg.get(r.facility_id, 0) + r.risk_score
    return {"points": [{"lat": facs[k].lat, "lng": facs[k].lng, "weight": round(v, 1)} for k, v in agg.items() if v > 0]}


@router.get("/forecasts/{facility_id}/{abo_rh}/{component}")
async def forecast(facility_id: int, abo_rh: str, component: str, history_days: int = Query(90, le=365),
                   session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    await assert_facility(session, p, facility_id)
    abo_rh = abo_rh.replace(" ", "+")  # '+' arrives as space when not URL-encoded
    start = today_ist() - timedelta(days=history_days)
    hist = (await session.execute(
        select(ConsumptionDaily).where(ConsumptionDaily.facility_id == facility_id, ConsumptionDaily.abo_rh == abo_rh,
                                       ConsumptionDaily.component == component, ConsumptionDaily.date >= start)
        .order_by(ConsumptionDaily.date))).scalars().all()
    fc = (await session.execute(
        select(DemandForecast).where(DemandForecast.facility_id == facility_id, DemandForecast.abo_rh == abo_rh,
                                     DemandForecast.component == component).order_by(DemandForecast.target_date))).scalars().all()
    if not fc and not hist:
        raise HTTPException(404, "no data for this series")
    risk_rows = [r for r in await latest_risk(session, {facility_id}) if r.abo_rh == abo_rh and r.component == component]
    return {
        "facility_id": facility_id, "abo_rh": abo_rh, "component": component,
        "history": [{"date": h.date, "units": h.units_issued, "emergency": h.units_emergency,
                     "scheduled": h.units_scheduled, "event": h.is_event_day, "quality": h.data_quality} for h in hist],
        "forecast": [{"date": f.target_date, "q10": f.q10, "q50": f.q50, "q90": f.q90, "mean": f.mean if f.mean is not None else f.q50,
                      "scheduled": f.scheduled_units} for f in fc],
        "model": fc[0].model_name if fc else None, "model_version": fc[0].model_version if fc else None,
        "drivers": (fc[0].drivers or []) if fc else [],
        "risk": {k: getattr(risk_rows[0], k) for k in ("p_stockout_24", "p_stockout_48", "p_stockout_72", "tts_p10",
                                                       "tts_p50", "usable_units", "severity", "confidence", "days_cover")}
        if risk_rows else None,
    }


@router.get("/availability/search")
async def search(abo_rh: str, component: str, facility_id: int | None = None, lat: float | None = None,
                 lng: float | None = None, radius_km: float = Query(50, le=200), include_compatible: bool = True,
                 irradiated: bool = False, cmv_safe: bool = False,
                 session: AsyncSession = Depends(get_session), p: Principal = Depends(current_user)) -> dict:
    """Network-wide availability (aggregate counts only, no unit-level data from other facilities)."""
    abo_rh = abo_rh.replace(" ", "+")
    origin_id = facility_id or p.facility_id
    if origin_id:
        f = await session.get(Facility, origin_id)
        if f is None:
            raise HTTPException(404, "facility not found")
        lat, lng = f.lat, f.lng
    if lat is None or lng is None:
        lat, lng = 28.6139, 77.2090
    book = await load_rulebook(session)
    res = await availability.search(session, book, abo_rh, component, lat, lng, radius_km, include_compatible,
                                    exclude_facility=origin_id, irradiated=irradiated, cmv_safe=cmv_safe)
    return {"as_of": now_utc().isoformat(), "query": {"abo_rh": abo_rh, "component": component, "radius_km": radius_km},
            "results": res}

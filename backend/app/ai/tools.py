"""Read-only tools the copilot may call. Each is scoped by the caller's role, returns JSON-safe data
with an `as_of` timestamp, and never mutates state (writes always need a human in the UI)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.guards import fence_untrusted
from app.db.models import Alert, Facility, TransferRequest
from app.domain.compat import load_rulebook
from app.domain.stock import freshness_hours, status_counts
from app.security import Principal
from app.services import availability
from app.services.risk import latest_risk
from app.services.scope import allowed_facilities, network_center

GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
COMPS = ["RBC", "PLT", "FFP", "CRYO"]

DECLARATIONS = [
    {"name": "get_risk_summary", "description": "Top blood shortage risks (probability of stockout, time to stockout) in the user's scope.",
     "parameters": {"type": "object", "properties": {
         "abo_rh": {"type": "string", "enum": GROUPS}, "component": {"type": "string", "enum": COMPS},
         "limit": {"type": "integer", "description": "max rows, default 8"}}}},
    {"name": "get_facility_inventory", "description": "Live usable stock by blood group and component for one facility (by code like LH-03 or by name).",
     "parameters": {"type": "object", "properties": {"facility": {"type": "string"}}, "required": ["facility"]}},
    {"name": "find_available_units", "description": "Find usable units of a blood group/component near a facility, including compatible alternatives.",
     "parameters": {"type": "object", "properties": {
         "abo_rh": {"type": "string", "enum": GROUPS}, "component": {"type": "string", "enum": COMPS},
         "near_facility": {"type": "string"}, "radius_km": {"type": "number"}}, "required": ["abo_rh", "component"]}},
    {"name": "list_alerts", "description": "Open shortage / expiry / data-quality alerts in scope.",
     "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "get_transfer_options", "description": "Optimizer transfer proposals (pending human approval) with ETA and reasons.",
     "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
]
ALLOWLIST = {d["name"] for d in DECLARATIONS}


def _as_of() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


async def _facilities(session: AsyncSession, p: Principal) -> dict[int, Facility]:
    allowed = await allowed_facilities(session, p)
    q = select(Facility)
    if allowed is not None:
        q = q.where(Facility.id.in_(allowed or {-1}))
    return {f.id: f for f in (await session.execute(q)).scalars()}


async def _resolve(session: AsyncSession, facs: dict[int, Facility], ref: str | None) -> Facility | None:
    if not ref:
        return None
    ref_l = ref.strip().lower()
    for f in facs.values():
        if f.code.lower() == ref_l or ref_l in f.name.lower():
            return f
    return None


async def get_risk_summary(session: AsyncSession, p: Principal, abo_rh: str | None = None,
                           component: str | None = None, limit: int = 8) -> dict:
    facs = await _facilities(session, p)
    rows = [r for r in await latest_risk(session, set(facs)) if (not abo_rh or r.abo_rh == abo_rh)
            and (not component or r.component == component)]
    rows.sort(key=lambda r: -r.risk_score)
    return {"as_of": rows[0].created_at.isoformat(timespec="seconds") if rows else _as_of(), "risks": [
        {"facility": facs[r.facility_id].name, "code": facs[r.facility_id].code, "abo_rh": r.abo_rh,
         "component": r.component, "severity": r.severity, "p_stockout_24h_pct": round(r.p_stockout_24 * 100),
         "p_stockout_48h_pct": round(r.p_stockout_48 * 100), "median_hours_to_stockout": round(r.tts_p50) if r.tts_p50 else None,
         "usable_units": r.usable_units, "confidence_pct": round(r.confidence * 100)}
        for r in rows[: max(1, min(limit or 8, 20))]]}


async def get_facility_inventory(session: AsyncSession, p: Principal, facility: str) -> dict:
    facs = await _facilities(session, p)
    f = await _resolve(session, facs, facility)
    if f is None:
        return {"error": "facility not found in your scope", "as_of": _as_of()}
    counts = await status_counts(session, {f.id})
    stock = {f"{g} {c}": v.get("available", 0) for (_, g, c), v in sorted(counts.items()) if v.get("available")}
    return {"as_of": _as_of(), "facility": f.name, "code": f.code, "hours_since_last_update": round(freshness_hours(f) or 0, 1),
            "available_units": stock, "facility_note": fence_untrusted(f.note)}


async def find_available_units(session: AsyncSession, p: Principal, abo_rh: str, component: str,
                               near_facility: str | None = None, radius_km: float = 50) -> dict:
    facs_scope = await _facilities(session, p)
    all_facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    origin = await _resolve(session, facs_scope, near_facility) or (all_facs.get(p.facility_id) if p.facility_id else None)
    lat, lng = (origin.lat, origin.lng) if origin else await network_center(session)
    book = await load_rulebook(session)
    res = await availability.search(session, book, abo_rh, component, lat, lng, radius_km or 50,
                                    exclude_facility=origin.id if origin else None, limit=8)
    return {"as_of": _as_of(), "near": origin.name if origin else "network centre", "results": [
        {k: r[k] for k in ("facility_name", "abo_rh", "units", "eta_minutes", "distance_km", "earliest_expiry_h",
                           "needs_clinician_approval")} for r in res]}


async def list_alerts(session: AsyncSession, p: Principal, limit: int = 10) -> dict:
    allowed = await allowed_facilities(session, p)
    q = select(Alert).where(Alert.status.in_(("open", "ack"))).order_by(Alert.last_fired_at.desc())
    if allowed is not None:
        q = q.where(Alert.facility_id.in_(allowed or {-1}))
    rows = (await session.execute(q.limit(max(1, min(limit or 10, 25))))).scalars().all()
    return {"as_of": _as_of(), "alerts": [{"severity": a.severity, "kind": a.kind, "message": a.message,
                                           "status": a.status} for a in rows]}


async def get_transfer_options(session: AsyncSession, p: Principal, limit: int = 8) -> dict:
    allowed = await allowed_facilities(session, p)
    q = select(TransferRequest).where(TransferRequest.status == "proposed").order_by(TransferRequest.id)
    if allowed is not None:
        ids = allowed or {-1}
        q = q.where(or_(TransferRequest.to_facility_id.in_(ids), TransferRequest.from_facility_id.in_(ids)))
    facs = {f.id: f for f in (await session.execute(select(Facility))).scalars()}
    rows = (await session.execute(q.limit(max(1, min(limit or 8, 20))))).scalars().all()
    return {"as_of": _as_of(), "proposals": [
        {"id": t.id, "from": facs[t.from_facility_id].name, "to": facs[t.to_facility_id].name, "abo_rh": t.abo_rh,
         "component": t.component, "quantity": t.quantity, "eta_minutes": round(t.eta_minutes),
         "needs_clinician_approval": t.needs_clinician_approval,
         "saves_shortage_units": t.reason_json.get("saves", {}).get("shortage_units"),
         "saves_wastage_units": t.reason_json.get("saves", {}).get("wastage_units")} for t in rows]}


IMPLS = {
    "get_risk_summary": get_risk_summary, "get_facility_inventory": get_facility_inventory,
    "find_available_units": find_available_units, "list_alerts": list_alerts,
    "get_transfer_options": get_transfer_options,
}


async def call_tool(session: AsyncSession, p: Principal, name: str, args: dict) -> dict:
    if name not in ALLOWLIST:
        return {"error": f"tool {name} is not allowed"}
    import inspect

    fn = IMPLS[name]
    params = set(inspect.signature(fn).parameters) - {"session", "p"}
    clean = {k: v for k, v in (args or {}).items() if k in params}
    try:
        return await fn(session, p, **clean)
    except TypeError as exc:
        return {"error": f"bad arguments: {exc}"}

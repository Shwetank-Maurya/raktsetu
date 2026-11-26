"""Mass-Casualty Stress Test: inject an incident on the map and see which facilities break and what
the network response plan looks like. What-if only: nothing is persisted."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppConfig, Facility
from app.domain.compat import RuleBook
from app.domain.rules import GROUP_MIX, SEVERITY_ORDER
from app.optimizer.routes import haversine_km
from app.schemas import IncidentIn
from app.services.planning import build_plan
from app.services.risk import compute_risk, latest_risk

DEFAULT_ASSUMPTIONS = {
    "severity_mix": {"critical": 0.2, "serious": 0.3, "minor": 0.5},
    "units_per_casualty": {
        "critical": {"RBC": 6, "FFP": 4, "PLT": 1, "CRYO": 0.5},
        "serious": {"RBC": 2, "FFP": 1, "PLT": 0.2, "CRYO": 0},
        "minor": {"RBC": 0.1, "FFP": 0, "PLT": 0, "CRYO": 0},
    },
    "emergency_o_neg_share": 0.15,  # un-crossmatched O- released before typing
    "receiving_weight": {"trauma": 3.0, "large": 2.0, "small": 0.3, "maternity": 0.2, "bank": 0.0},
    "note": "Assumptions are illustrative and editable; confirm with local trauma protocols.",
}


async def get_assumptions(session: AsyncSession) -> dict:
    row = await session.get(AppConfig, "incident_assumptions")
    return row.value if row else DEFAULT_ASSUMPTIONS


def allocate_casualties(facs: list[Facility], req: IncidentIn, a: dict) -> dict[int, dict[str, float]]:
    """Split casualties across receiving hospitals by capability weight / distance. Critical
    patients only go to trauma or large hospitals."""
    mix = req.severity_mix or a["severity_mix"]
    near = [(f, haversine_km((req.lat, req.lng), (f.lat, f.lng))) for f in facs if f.type == "hospital"]
    near = [(f, d) for f, d in near if d <= req.radius_km] or sorted(near, key=lambda x: x[1])[:3]
    out: dict[int, dict[str, float]] = {}
    for sev, share in mix.items():
        n = req.casualties * share
        elig = [(f, d) for f, d in near if sev != "critical" or f.subtype in ("trauma", "large")] or near
        weights = [a["receiving_weight"].get(f.subtype, 0.5) / (1 + d / 5) for f, d in elig]
        tot = sum(weights) or 1.0
        for (f, _), w in zip(elig, weights, strict=True):
            out.setdefault(f.id, {}).setdefault(sev, 0.0)
            out[f.id][sev] += n * w / tot
    return out


def extra_demand(alloc: dict[int, dict[str, float]], a: dict) -> dict[tuple[int, str, str], list[float]]:
    out: dict[tuple[int, str, str], list[float]] = {}
    for fid, sevs in alloc.items():
        for sev, n in sevs.items():
            for comp, per in a["units_per_casualty"][sev].items():
                units = n * per
                if units <= 0:
                    continue
                o_neg = units * a["emergency_o_neg_share"] if comp == "RBC" and sev == "critical" else 0.0
                for g, share in GROUP_MIX.items():
                    u = (units - o_neg) * share + (o_neg if g == "O-" else 0)
                    key = (fid, g, comp)
                    day0 = out.setdefault(key, [0.0])
                    day0[0] += u
    return out


async def simulate_incident(session: AsyncSession, book: RuleBook, req: IncidentIn) -> dict:
    a = await get_assumptions(session)
    facs = list((await session.execute(select(Facility).where(Facility.active.is_(True)))).scalars())
    fmap = {f.id: f for f in facs}
    alloc = allocate_casualties(facs, req, a)
    extra = extra_demand(alloc, a)
    baseline = {(r.facility_id, r.abo_rh, r.component): r.severity for r in await latest_risk(session)}
    what_if = await compute_risk(session, book, persist=False, extra_demand=extra, n_paths=500)
    affected = []
    for r in what_if:
        key = (r["facility_id"], r["abo_rh"], r["component"])
        before = baseline.get(key, "low")
        if SEVERITY_ORDER[r["severity"]] > SEVERITY_ORDER[before] and SEVERITY_ORDER[r["severity"]] >= 2:
            f = fmap[r["facility_id"]]
            affected.append({"facility_id": f.id, "name": f.name, "lat": f.lat, "lng": f.lng, "abo_rh": r["abo_rh"],
                             "component": r["component"], "before": before, "after": r["severity"],
                             "p_stockout_24": r["p_stockout_24"], "tts_p50": r["tts_p50"],
                             "extra_units": round(sum(extra.get(key, [0])), 1)})
    plan_result, _ = await build_plan(session, book, what_if, use_api=False)
    # The response plan focuses on what the incident made urgent; routine medium moves stay on the Transfer Desk.
    sev_after = {(r["facility_id"], r["abo_rh"], r["component"]): r["severity"] for r in what_if}
    urgent = lambda f, g, c: SEVERITY_ORDER.get(sev_after.get((f, g, c), "low"), 0) >= 2  # noqa: E731
    plan_result.proposals = [p for p in plan_result.proposals
                             if urgent(p.to_facility_id, p.requested_for_abo_rh or p.abo_rh, p.component)]
    plan_result.deficits = [d for d in plan_result.deficits if d.get("severity") in ("high", "critical")]
    plan_result.stats["proposals_shown"] = len(plan_result.proposals)
    affected.sort(key=lambda x: (-SEVERITY_ORDER[x["after"]], x["tts_p50"] or 1e9))
    return {
        "incident": req.model_dump(),
        "assumptions": a,
        "casualty_allocation": [{"facility_id": fid, "name": fmap[fid].name, "lat": fmap[fid].lat, "lng": fmap[fid].lng,
                                 **{k: round(v, 1) for k, v in sevs.items()}} for fid, sevs in alloc.items()],
        "total_extra_units": {c: round(sum(v[0] for (f, g, cc), v in extra.items() if cc == c), 1)
                              for c in ("RBC", "FFP", "PLT", "CRYO")},
        "affected": affected,
        "facilities_breaking": len({x["facility_id"] for x in affected}),
        "plan": [{"from_facility_id": p.from_facility_id, "from_name": fmap[p.from_facility_id].name,
                  "to_facility_id": p.to_facility_id, "to_name": fmap[p.to_facility_id].name,
                  "abo_rh": p.abo_rh, "component": p.component, "quantity": p.quantity, "eta_minutes": p.eta_minutes,
                  "needs_clinician_approval": p.needs_clinician_approval,
                  "from_lat": fmap[p.from_facility_id].lat, "from_lng": fmap[p.from_facility_id].lng,
                  "to_lat": fmap[p.to_facility_id].lat, "to_lng": fmap[p.to_facility_id].lng}
                 for p in plan_result.proposals],
        "unmet": plan_result.deficits,
        "plan_stats": plan_result.stats,
    }

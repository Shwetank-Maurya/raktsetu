"""Alert engine (blueprint B6.5): severity tiers, dedupe, 6 h cooldown, escalation after 30 min
unacknowledged Critical, auto-resolve after two consecutive calm cycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, Facility
from app.domain.ledger import now_utc
from app.services import realtime

ALERT_ORDER = {"info": 0, "warning": 1, "high": 2, "critical": 3}
# Medium risk is visible in the risk table but does not raise an alert (alert-fatigue control, #45).
RISK_TO_ALERT = {"critical": "critical", "high": "high"}
COOLDOWN = timedelta(hours=6)
ESCALATE_AFTER = timedelta(minutes=30)
RESOLVE_AFTER_CALM_CYCLES = 2


@dataclass
class Candidate:
    dedupe_key: str
    kind: str
    severity: str
    message: str
    facility_id: int | None = None
    region_id: int | None = None
    abo_rh: str | None = None
    component: str | None = None
    details: dict | None = None


def _fmt_h(h: float | None) -> str:
    if h is None:
        return "beyond 7 days"
    return f"{h:.0f} h" if h < 48 else f"{h / 24:.1f} days"


def candidates_from_risk(rows: list[dict], facs: dict[int, Facility]) -> list[Candidate]:
    out = []
    for r in rows:
        sev = RISK_TO_ALERT.get(r["severity"])
        if not sev:
            continue
        f = facs.get(r["facility_id"])
        name = f.name if f else f"facility {r['facility_id']}"
        msg = (f"{name}: {r['abo_rh']} {r['component']} - {r['p_stockout_24'] * 100:.0f}% chance of stockout in 24 h, "
               f"median time to stockout {_fmt_h(r['tts_p50'])} (resupply lead {r['lead_time_h']:.1f} h).")
        out.append(Candidate(
            f"risk:{r['facility_id']}:{r['abo_rh']}:{r['component']}", "stockout_risk", sev, msg,
            r["facility_id"], f.region_id if f else None, r["abo_rh"], r["component"],
            {k: r[k] for k in ("p_stockout_24", "p_stockout_48", "tts_p50", "usable_units", "confidence", "event_mode")},
        ))
    for r in rows:
        f = facs.get(r["facility_id"])
        name = f.name if f else f"facility {r['facility_id']}"
        if r.get("expected_wastage", 0) >= 3:
            out.append(Candidate(
                f"expiry:{r['facility_id']}:{r['abo_rh']}:{r['component']}", "near_expiry", "warning",
                f"{name}: about {r['expected_wastage']:.0f} {r['abo_rh']} {r['component']} units are projected to expire unused. "
                "Use it or move it.", r["facility_id"], f.region_id if f else None, r["abo_rh"], r["component"],
                {"expected_wastage": r["expected_wastage"]}))
    return out


def stale_candidates(facs: dict[int, Facility], stale_hours: dict[int, float]) -> list[Candidate]:
    return [Candidate(f"silent:{fid}", "data_silent", "high" if h > 24 else "warning",
                      f"{facs[fid].name} has not reported stock for {h:.0f} h. Forecasts use pessimistic assumptions.",
                      fid, facs[fid].region_id, details={"hours_silent": round(h, 1)})
            for fid, h in stale_hours.items() if fid in facs]


def deficit_candidates(deficits: list[dict], facs: dict[int, Facility]) -> list[Candidate]:
    out = []
    for d in deficits:
        if d.get("severity") not in ("high", "critical"):
            continue
        f = facs.get(d["facility_id"])
        out.append(Candidate(
            f"deficit:{d['facility_id']}:{d['abo_rh']}:{d['component']}", "regional_deficit",
            "critical" if d.get("severity") == "critical" else "high",
            f"No feasible donor for {d['unmet_units']} {d['abo_rh']} {d['component']} units at "
            f"{f.name if f else d['facility_id']}. Trigger a donor campaign and escalate.",
            d["facility_id"], f.region_id if f else None, d["abo_rh"], d["component"], d))
    return out


def _to_dict(a: Alert) -> dict:
    return {"id": a.id, "dedupe_key": a.dedupe_key, "facility_id": a.facility_id, "region_id": a.region_id,
            "abo_rh": a.abo_rh, "component": a.component, "severity": a.severity, "kind": a.kind,
            "message": a.message, "status": a.status, "escalated": a.escalated_at is not None}


async def evaluate(session: AsyncSession, cands: list[Candidate], managed_kinds: set[str]) -> dict:
    now = now_utc()
    active = (await session.execute(select(Alert).where(Alert.status.in_(("open", "ack"))))).scalars().all()
    by_key = {a.dedupe_key: a for a in active}
    fired: list[Alert] = []
    seen = set()
    stats = {"created": 0, "refired": 0, "resolved": 0, "escalated": 0, "suppressed": 0}
    for c in cands:
        seen.add(c.dedupe_key)
        a = by_key.get(c.dedupe_key)
        if a is None:
            a = Alert(dedupe_key=c.dedupe_key, facility_id=c.facility_id, region_id=c.region_id, abo_rh=c.abo_rh,
                      component=c.component, severity=c.severity, kind=c.kind, message=c.message, details=c.details,
                      first_seen=now, last_seen=now, last_fired_at=now)
            session.add(a)
            fired.append(a)
            stats["created"] += 1
            continue
        a.last_seen, a.below_count, a.message, a.details = now, 0, c.message, c.details
        if ALERT_ORDER[c.severity] > ALERT_ORDER[a.severity]:
            a.severity, a.last_fired_at, a.status = c.severity, now, "open"  # re-fire on escalation
            fired.append(a)
            stats["refired"] += 1
        elif a.status == "open" and now - a.last_fired_at >= COOLDOWN:
            a.last_fired_at = now
            fired.append(a)
            stats["refired"] += 1
        else:
            stats["suppressed"] += 1
    for a in active:
        if a.dedupe_key in seen or a.kind not in managed_kinds:
            continue
        a.below_count += 1
        if a.below_count >= RESOLVE_AFTER_CALM_CYCLES:
            a.status, a.resolved_at = "resolved", now
            stats["resolved"] += 1
            realtime.mirror_alert(_to_dict(a))
    for a in active:
        if (a.status == "open" and a.severity == "critical" and a.escalated_at is None
                and now - a.first_seen >= ESCALATE_AFTER):
            a.escalated_at = now
            a.message = "[ESCALATED to regional coordinator] " + a.message
            fired.append(a)
            stats["escalated"] += 1
    await session.flush()
    for a in fired:
        d = _to_dict(a)
        realtime.mirror_alert(d)
        realtime.push_alert(d)
        await realtime.email_alert(d)
    return stats

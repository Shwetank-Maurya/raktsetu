"""Transfer lifecycle state machine.

proposed -> approved -> dispatched -> received
proposed -> rejected | superseded
approved -> cancelled (units released) | expired (not dispatched in time)
dispatched -> cancelled (units returned to source)

Units are locked when a transfer is approved (status reserved, transfer_id set) so neither side
counts them as usable, move to in_transit on dispatch (excluded from both sides), and become
available at the destination on receipt.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BloodUnit, TransferRequest
from app.domain.audit import audit
from app.domain.compat import RuleBook
from app.domain.errors import Forbidden, InsufficientStock, InvalidTransition, NotFound
from app.domain.ledger import _set_status, now_utc, system_event
from app.security import Principal

TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"approved", "rejected", "superseded"},
    "approved": {"dispatched", "cancelled", "expired"},
    "dispatched": {"received", "cancelled"},
    "received": set(),
    "rejected": set(),
    "cancelled": set(),
    "superseded": set(),
    "expired": set(),
}
APPROVAL_TTL = timedelta(hours=6)


def _snap(t: TransferRequest) -> dict:
    return {"status": t.status, "quantity": t.quantity, "unit_ids": list(t.unit_ids or [])}


def _check(t: TransferRequest, new: str) -> None:
    if new not in TRANSITIONS[t.status]:
        raise InvalidTransition(f"cannot move transfer from {t.status} to {new}")


async def get_locked(session: AsyncSession, transfer_id: int) -> TransferRequest:
    t = await session.get(TransferRequest, transfer_id, with_for_update=True)
    if t is None:
        raise NotFound("transfer not found")
    return t


def _can_act(actor: Principal, t: TransferRequest, action: str) -> bool:
    if actor.is_network_role:
        return True
    if actor.role == "bank_manager" and action in ("dispatch", "cancel") and actor.facility_id == t.from_facility_id:
        return True
    if action == "receive" and actor.facility_id == t.to_facility_id:
        return True
    return False


async def approve(session: AsyncSession, actor: Principal, transfer_id: int, book: RuleBook,
                  clinician_ack: bool = False) -> TransferRequest:
    t = await get_locked(session, transfer_id)
    if not _can_act(actor, t, "approve"):
        raise Forbidden("only a regional coordinator or admin can approve transfers")
    _check(t, "approved")
    if t.needs_clinician_approval and not clinician_ack:
        raise Forbidden("this is a compatible substitution and needs clinician sign-off (clinician_ack=true)")
    shelf = book.shelf[t.component]
    min_expiry = now_utc() + timedelta(minutes=t.eta_minutes) + timedelta(hours=shelf.min_life_on_arrival_hours)
    # Re-pick units at approval time: prefer the proposed ones, fall back to any FEFO-feasible unit.
    q = (select(BloodUnit)
         .where(BloodUnit.facility_id == t.from_facility_id, BloodUnit.abo_rh == t.abo_rh,
                BloodUnit.component == t.component, BloodUnit.status == "available",
                BloodUnit.expires_at >= min_expiry)
         .order_by(BloodUnit.id.in_(t.unit_ids or []).desc(), BloodUnit.expires_at)
         .limit(t.quantity).with_for_update(skip_locked=True))
    units = list((await session.execute(q)).scalars().all())
    if len(units) < t.quantity:
        raise InsufficientStock(
            f"source now has only {len(units)} feasible units (needs {t.quantity}); re-plan", available=len(units))
    before = _snap(t)
    await _set_status(session, units, "reserved", transfer_id=t.id)
    t.unit_ids = [u.id for u in units]
    t.status = "approved"
    t.approved_by = actor.uid
    await system_event(session, t.from_facility_id, "transfer_lock", units, f"transfer:{t.id}:approve")
    await audit(session, actor, "transfer.approve", "transfer", t.id, before, _snap(t))
    return t


async def reject(session: AsyncSession, actor: Principal, transfer_id: int, note: str | None = None) -> TransferRequest:
    t = await get_locked(session, transfer_id)
    if not actor.is_network_role:
        raise Forbidden("only a regional coordinator or admin can reject proposals")
    _check(t, "rejected")
    before = _snap(t)
    t.status = "rejected"
    t.reason_json = (t.reason_json or {}) | {"rejection_note": note}
    await audit(session, actor, "transfer.reject", "transfer", t.id, before, _snap(t))
    return t


async def dispatch(session: AsyncSession, actor: Principal, transfer_id: int) -> TransferRequest:
    t = await get_locked(session, transfer_id)
    if not _can_act(actor, t, "dispatch"):
        raise Forbidden("not allowed to dispatch this transfer")
    _check(t, "dispatched")
    units = await _transfer_units(session, t, "reserved")
    before = _snap(t)
    await _set_status(session, units, "in_transit")
    t.status, t.dispatched_at = "dispatched", now_utc()
    await system_event(session, t.from_facility_id, "transfer_out", units, f"transfer:{t.id}:dispatch")
    await audit(session, actor, "transfer.dispatch", "transfer", t.id, before, _snap(t))
    return t


async def receive(session: AsyncSession, actor: Principal, transfer_id: int) -> TransferRequest:
    t = await get_locked(session, transfer_id)
    if not _can_act(actor, t, "receive"):
        raise Forbidden("not allowed to receive this transfer")
    _check(t, "received")
    units = await _transfer_units(session, t, "in_transit")
    before = _snap(t)
    now = now_utc()
    await _set_status(session, units, "available" , facility_id=t.to_facility_id, transfer_id=None)
    expired = [u for u in units if u.expires_at <= now]
    if expired:
        await _set_status(session, expired, "expired")
    t.status, t.received_at = "received", now
    await system_event(session, t.to_facility_id, "transfer_in", units, f"transfer:{t.id}:receive")
    await audit(session, actor, "transfer.receive", "transfer", t.id, before, _snap(t))
    return t


async def cancel(session: AsyncSession, actor: Principal, transfer_id: int, reason: str = "cancelled") -> TransferRequest:
    t = await get_locked(session, transfer_id)
    if not _can_act(actor, t, "cancel"):
        raise Forbidden("not allowed to cancel this transfer")
    target = "expired" if reason == "timeout" else "cancelled"
    _check(t, target)
    units = await _transfer_units(session, t, "reserved" if t.status == "approved" else "in_transit")
    before = _snap(t)
    # Released units go back to the source facility's usable stock.
    await _set_status(session, units, "available", transfer_id=None)
    t.status = target
    t.reason_json = (t.reason_json or {}) | {"cancel_reason": reason}
    await system_event(session, t.from_facility_id, "transfer_release", units, f"transfer:{t.id}:{target}")
    await audit(session, actor, f"transfer.{target}", "transfer", t.id, before, _snap(t))
    return t


async def _transfer_units(session: AsyncSession, t: TransferRequest, status: str) -> list[BloodUnit]:
    q = select(BloodUnit).where(BloodUnit.transfer_id == t.id, BloodUnit.status == status).with_for_update()
    return list((await session.execute(q)).scalars().all())


async def expire_stale_approvals(session: AsyncSession) -> int:
    """Approved but never dispatched within APPROVAL_TTL: release units (edge case #29)."""
    from app.security import SYSTEM

    ids = (await session.execute(
        select(TransferRequest.id).where(TransferRequest.status == "approved",
                                         TransferRequest.updated_at < now_utc() - APPROVAL_TTL)
    )).scalars().all()
    for tid in ids:
        await cancel(session, SYSTEM, tid, reason="timeout")
    return len(ids)


async def overdue_dispatched(session: AsyncSession) -> list[TransferRequest]:
    rows = (await session.execute(select(TransferRequest).where(TransferRequest.status == "dispatched"))).scalars().all()
    now = now_utc()
    return [t for t in rows if t.dispatched_at and now > t.dispatched_at + timedelta(minutes=2 * t.eta_minutes + 30)]

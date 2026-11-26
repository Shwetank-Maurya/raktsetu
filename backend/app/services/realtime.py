"""Live fan-out. Postgres LISTEN/NOTIFY does not work through Neon's pooler (edge case #37), so
browsers listen to Firestore instead. The backend is the only writer (see infra/firestore.rules).
FCM pushes High/Critical alerts to topic subscribers; Brevo email is an optional extra channel.
Every channel is optional and failures never break the request that triggered them."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
_db = None


def _firestore():
    global _db
    s = get_settings()
    if not s.firestore_enabled:
        return None
    if _db is None:
        try:
            import firebase_admin
            from firebase_admin import firestore

            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={"projectId": s.firebase_project_id})
            _db = firestore.client()
        except Exception as exc:  # noqa: BLE001
            log.warning("firestore unavailable: %s", exc)
            return None
    return _db


def mirror_alert(alert: dict) -> None:
    db = _firestore()
    if db is None:
        return
    try:
        db.collection("alerts").document(str(alert["id"])).set(alert | {"updated_at": datetime.now(UTC)})
    except Exception as exc:  # noqa: BLE001
        log.warning("firestore alert mirror failed: %s", exc)


def mirror_stock_summaries(summaries: list[dict]) -> None:
    db = _firestore()
    if db is None:
        return
    try:
        batch = db.batch()
        for s in summaries:
            batch.set(db.collection("stock_summary").document(str(s["facility_id"])), s | {"updated_at": datetime.now(UTC)})
        batch.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("firestore stock mirror failed: %s", exc)


def mirror_event(kind: str, payload: dict) -> None:
    """Small 'something changed' pings (transfer approved, stock changed) so other browsers refetch."""
    db = _firestore()
    if db is None:
        return
    try:
        db.collection("events").document(kind).set(payload | {"at": datetime.now(UTC)})
    except Exception as exc:  # noqa: BLE001
        log.warning("firestore event mirror failed: %s", exc)


def push_alert(alert: dict) -> None:
    s = get_settings()
    if not s.fcm_enabled or alert.get("severity") not in ("high", "critical"):
        return
    try:
        from firebase_admin import messaging

        _firestore()  # ensures firebase app init
        topic = f"region-{alert.get('region_id') or 1}"
        messaging.send(messaging.Message(
            topic=topic,
            notification=messaging.Notification(title=f"RaktSetu {alert['severity'].upper()}", body=alert["message"][:180]),
            data={"alert_id": str(alert["id"]), "severity": alert["severity"]},
        ))
    except Exception as exc:  # noqa: BLE001
        log.warning("fcm push failed: %s", exc)


async def email_alert(alert: dict) -> None:
    s = get_settings()
    if not (s.brevo_api_key and s.alert_email_to) or alert.get("severity") != "critical":
        return
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post("https://api.brevo.com/v3/smtp/email", headers={"api-key": s.brevo_api_key}, json={
                "sender": {"email": s.alert_email_from, "name": "RaktSetu"},
                "to": [{"email": s.alert_email_to}],
                "subject": f"[RaktSetu CRITICAL] {alert['message'][:80]}",
                "textContent": alert["message"],
            })
    except Exception as exc:  # noqa: BLE001
        log.warning("brevo email failed: %s", exc)

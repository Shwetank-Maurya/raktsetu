"""SQLAlchemy models. The ledger (inventory_events) is the truth; blood_units.status is a
projection maintained only by app/domain/ledger.py inside the same transaction."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ABO_RH = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")
COMPONENTS = ("RBC", "PLT", "FFP", "CRYO")
UNIT_STATUSES = ("available", "reserved", "quarantined", "in_transit", "issued", "expired", "discarded")
FACILITY_TYPES = ("hospital", "blood_bank")

_group_check = "abo_rh IN ('O-','O+','A-','A+','B-','B+','AB-','AB+')"
_comp_check = "component IN ('RBC','PLT','FFP','CRYO')"


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSONB, list: JSONB}


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    level: Mapped[str] = mapped_column(String(20))  # state | district
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint("type IN ('hospital','blood_bank')", name="ck_facility_type"),
        CheckConstraint("lat BETWEEN -90 AND 90 AND lng BETWEEN -180 AND 180", name="ck_facility_geo"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(20))
    subtype: Mapped[str] = mapped_column(String(30), default="general")  # large|small|trauma|maternity|bank
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    beds: Mapped[int] = mapped_column(Integer, default=0)
    has_component_separation: Mapped[bool] = mapped_column(Boolean, default=False)
    is_trauma_centre: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_capacity: Mapped[int] = mapped_column(Integer, default=200)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)  # free text: treated as untrusted data by the copilot


class BloodUnit(Base):
    __tablename__ = "blood_units"
    __table_args__ = (
        CheckConstraint(_group_check, name="ck_unit_group"),
        CheckConstraint(_comp_check, name="ck_unit_component"),
        CheckConstraint("expires_at > collected_at", name="ck_unit_expiry_after_collection"),
        CheckConstraint("volume_ml BETWEEN 10 AND 600", name="ck_unit_volume"),
        CheckConstraint(
            "status IN ('available','reserved','quarantined','in_transit','issued','expired','discarded')",
            name="ck_unit_status",
        ),
        Index("ix_units_stock", "facility_id", "abo_rh", "component", "status", "expires_at"),
        Index("ix_units_donation", "donation_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    donation_id: Mapped[str] = mapped_column(String(40))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    abo_rh: Mapped[str] = mapped_column(String(3))
    component: Mapped[str] = mapped_column(String(4))
    irradiated: Mapped[bool] = mapped_column(Boolean, default=False)
    leukoreduced: Mapped[bool] = mapped_column(Boolean, default=False)
    cmv_safe: Mapped[bool] = mapped_column(Boolean, default=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    volume_ml: Mapped[int] = mapped_column(Integer, default=350)
    status: Mapped[str] = mapped_column(String(12), default="available")
    reservation_id: Mapped[str | None] = mapped_column(String(36))
    transfer_id: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InventoryEvent(Base):
    __tablename__ = "inventory_events"
    __table_args__ = (
        UniqueConstraint("facility_id", "idempotency_key", name="uq_event_idem"),
        CheckConstraint("quantity >= 0", name="ck_event_qty"),
        Index("ix_events_facility_time", "facility_id", "event_time"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    unit_id: Mapped[str | None] = mapped_column(String(36))
    type: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    abo_rh: Mapped[str | None] = mapped_column(String(3))
    component: Mapped[str | None] = mapped_column(String(4))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(10), default="api")  # ui | api | ocr | system | seed
    payload: Mapped[dict | None] = mapped_column(JSONB)


class RejectedEntry(Base):
    __tablename__ = "rejected_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsumptionDaily(Base):
    __tablename__ = "consumption_daily"
    __table_args__ = (
        CheckConstraint("units_issued >= 0", name="ck_cons_nonneg"),
        Index("ix_cons_series", "facility_id", "abo_rh", "component", "date"),
    )
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    abo_rh: Mapped[str] = mapped_column(String(3), primary_key=True)
    component: Mapped[str] = mapped_column(String(4), primary_key=True)
    units_issued: Mapped[int] = mapped_column(Integer, default=0)
    units_emergency: Mapped[int] = mapped_column(Integer, default=0)
    units_scheduled: Mapped[int] = mapped_column(Integer, default=0)
    is_event_day: Mapped[bool] = mapped_column(Boolean, default=False)
    data_quality: Mapped[str] = mapped_column(String(12), default="ok")  # ok | imputed | late


class ScheduledDemand(Base):
    __tablename__ = "scheduled_demand"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    patient_cohort: Mapped[str] = mapped_column(String(40))  # e.g. thalassemia (no patient identity)
    abo_rh: Mapped[str] = mapped_column(String(3))
    component: Mapped[str] = mapped_column(String(4))
    due_date: Mapped[date] = mapped_column(Date)
    units: Mapped[int] = mapped_column(Integer)


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"
    __table_args__ = (Index("ix_fc_series", "facility_id", "abo_rh", "component", "target_date"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    abo_rh: Mapped[str] = mapped_column(String(3))
    component: Mapped[str] = mapped_column(String(4))
    target_date: Mapped[date] = mapped_column(Date)
    q10: Mapped[float] = mapped_column(Float)
    q50: Mapped[float] = mapped_column(Float)
    q90: Mapped[float] = mapped_column(Float)
    mean: Mapped[float | None] = mapped_column(Float)  # expected demand (risk engine input)
    scheduled_units: Mapped[float] = mapped_column(Float, default=0)
    model_name: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str] = mapped_column(String(40))
    drivers: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    __table_args__ = (Index("ix_risk_latest", "facility_id", "abo_rh", "component", "created_at"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    abo_rh: Mapped[str] = mapped_column(String(3))
    component: Mapped[str] = mapped_column(String(4))
    usable_units: Mapped[int] = mapped_column(Integer)
    p_stockout_24: Mapped[float] = mapped_column(Float)
    p_stockout_48: Mapped[float] = mapped_column(Float)
    p_stockout_72: Mapped[float] = mapped_column(Float)
    tts_p10: Mapped[float | None] = mapped_column(Float)  # hours; null = no stockout in horizon
    tts_p50: Mapped[float | None] = mapped_column(Float)
    days_cover: Mapped[float] = mapped_column(Float)
    expected_wastage: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(10))  # low | medium | high | critical
    confidence: Mapped[float] = mapped_column(Float)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    lead_time_h: Mapped[float] = mapped_column(Float, default=2.0)
    model_used: Mapped[str] = mapped_column(String(40))
    event_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_dedupe", "dedupe_key", "status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(120))
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    region_id: Mapped[int | None] = mapped_column(Integer)
    abo_rh: Mapped[str | None] = mapped_column(String(3))
    component: Mapped[str | None] = mapped_column(String(4))
    severity: Mapped[str] = mapped_column(String(10))  # info | warning | high | critical
    kind: Mapped[str] = mapped_column(String(30))  # stockout_risk | data_silent | near_expiry | regional_deficit | anomaly
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | ack | resolved
    details: Mapped[dict | None] = mapped_column(JSONB)
    below_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(128))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    abo_rh: Mapped[str] = mapped_column(String(3))
    component: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active | released | consumed | expired
    purpose: Mapped[str | None] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransferRequest(Base):
    __tablename__ = "transfer_requests"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transfer_qty"),
        CheckConstraint("from_facility_id <> to_facility_id", name="ck_transfer_distinct"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(12), default="deficit")  # deficit | rescue | manual | incident
    from_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    to_facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    abo_rh: Mapped[str] = mapped_column(String(3))
    component: Mapped[str] = mapped_column(String(4))
    requested_for_abo_rh: Mapped[str | None] = mapped_column(String(3))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(12), default="proposed")
    eta_minutes: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    eta_source: Mapped[str] = mapped_column(String(20), default="haversine")
    min_life_on_arrival_h: Mapped[float] = mapped_column(Float)
    needs_clinician_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    reason_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), default="optimizer")
    approved_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Donor(Base):
    __tablename__ = "donors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_hash: Mapped[str] = mapped_column(String(64), unique=True)
    first_name: Mapped[str] = mapped_column(String(40))
    abo_rh: Mapped[str] = mapped_column(String(3))
    sex: Mapped[str] = mapped_column(String(1))
    last_donation_on: Mapped[date | None] = mapped_column(Date)
    consent: Mapped[bool] = mapped_column(Boolean, default=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    pin_code: Mapped[str] = mapped_column(String(6))
    lat: Mapped[float] = mapped_column(Float)  # PIN-centroid, never exact address
    lng: Mapped[float] = mapped_column(Float)
    region_id: Mapped[int | None] = mapped_column(Integer)
    preferred_lang: Mapped[str] = mapped_column(String(2), default="hi")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (UniqueConstraint("date", "name", name="uq_cal_date_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))  # festival | holiday | outbreak | incident
    name: Mapped[str] = mapped_column(String(120))
    region_id: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(30), default="static")  # static | google_calendar | manual
    note: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    actor_role: Mapped[str | None] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(60))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)  # scope:actor:key
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompatRule(Base):
    __tablename__ = "compat_rules"
    component: Mapped[str] = mapped_column(String(4), primary_key=True)
    donor_abo_rh: Mapped[str] = mapped_column(String(3), primary_key=True)
    recipient_abo_rh: Mapped[str] = mapped_column(String(3), primary_key=True)


class ShelfLifeRule(Base):
    __tablename__ = "shelf_life_rules"
    component: Mapped[str] = mapped_column(String(4), primary_key=True)
    shelf_life_hours: Mapped[float] = mapped_column(Float)
    min_usable_hours: Mapped[float] = mapped_column(Float)
    min_life_on_arrival_hours: Mapped[float] = mapped_column(Float)
    max_transit_hours: Mapped[float] = mapped_column(Float)
    storage: Mapped[str] = mapped_column(String(40))
    units_per_day_floor: Mapped[float] = mapped_column(Float, default=1.0)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(12), default="running")
    stats: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobLock(Base):
    """Lease lock for scheduled jobs. Session-level pg advisory locks are unsafe behind Neon's
    transaction-mode pooler, so overlapping runs are prevented with a row lease instead."""
    __tablename__ = "job_locks"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    holder: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # backtest | replay
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccessRequest(Base):
    """Self sign-up -> request a role at a facility -> coordinator/admin approves -> Firebase claims set."""
    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("requested_role IN ('hospital_user','bank_manager')", name="ck_access_role"),
        CheckConstraint("status IN ('pending','approved','rejected')", name="ck_access_status"),
        Index("ix_access_status", "status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(String(128), unique=True)
    email: Mapped[str | None] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(120))
    requested_role: Mapped[str] = mapped_column(String(30))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    note: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(128))
    decision_note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppConfig(Base):
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)

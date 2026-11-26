"""Pydantic request/response models (the OpenAPI contract the frontend client is generated from)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.rules import DEFAULT_SHELF_LIFE

AboRh = Literal["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
Component = Literal["RBC", "PLT", "FFP", "CRYO"]
EventType = Literal["receive", "issue", "discard", "quarantine", "release_quarantine", "recall"]

# Plausible single-unit volumes per component (catches unit/mL confusion).
VOLUME_RANGE = {"RBC": (150, 450), "PLT": (30, 400), "FFP": (150, 320), "CRYO": (10, 60)}
DEFAULT_VOLUME = {"RBC": 280, "PLT": 60, "FFP": 220, "CRYO": 25}


class UnitAttributes(BaseModel):
    irradiated: bool = False
    leukoreduced: bool = False
    cmv_safe: bool = False


class InventoryEventIn(BaseModel):
    type: EventType
    facility_id: int
    abo_rh: AboRh | None = None
    component: Component | None = None
    quantity: int = Field(1, ge=1, le=200)
    unit_ids: list[str] | None = Field(None, max_length=200)
    donation_id: str | None = Field(None, max_length=40)
    collected_at: datetime | None = None
    expires_at: datetime | None = None
    volume_ml: int | None = None
    attributes: UnitAttributes = Field(default_factory=UnitAttributes)
    emergency: bool = False
    event_time: datetime | None = None
    note: str | None = Field(None, max_length=500)

    @field_validator("collected_at", "expires_at", "event_time")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamps must include a timezone (UTC recommended)")
        return v

    @model_validator(mode="after")
    def _check(self) -> InventoryEventIn:
        now = datetime.now(UTC)
        if self.event_time:
            if self.event_time > now + timedelta(minutes=5):
                raise ValueError("event_time is in the future")
            if self.event_time < now - timedelta(days=30):
                raise ValueError("event_time is more than 30 days in the past")
        if self.type in ("receive", "issue", "discard") and not self.unit_ids:
            if not (self.abo_rh and self.component):
                raise ValueError(f"{self.type} needs abo_rh and component (or unit_ids)")
        if self.type in ("quarantine", "release_quarantine") and not self.unit_ids:
            raise ValueError(f"{self.type} needs unit_ids")
        if self.type == "recall" and not self.donation_id:
            raise ValueError("recall needs donation_id")
        if self.type == "receive":
            comp = self.component or "RBC"
            shelf = DEFAULT_SHELF_LIFE[comp]
            collected = self.collected_at or now
            expires = self.expires_at or collected + timedelta(hours=shelf.shelf_life_hours)
            if collected > now + timedelta(minutes=5):
                raise ValueError("collected_at is in the future")
            if expires <= collected:
                raise ValueError("expires_at must be after collected_at")
            if (expires - collected) > timedelta(hours=shelf.shelf_life_hours * 1.05):
                raise ValueError(f"expiry exceeds {comp} shelf life of {shelf.shelf_life_hours:.0f} h")
            if expires <= now:
                raise ValueError("unit is already expired")
            lo, hi = VOLUME_RANGE[comp]
            vol = self.volume_ml if self.volume_ml is not None else DEFAULT_VOLUME[comp]
            if not lo <= vol <= hi:
                raise ValueError(f"volume_ml {vol} outside plausible {comp} range {lo}-{hi} mL")
            self.collected_at, self.expires_at, self.volume_ml = collected, expires, vol
        return self


class ReservationIn(BaseModel):
    facility_id: int
    abo_rh: AboRh
    component: Component
    quantity: int = Field(ge=1, le=50)
    ttl_minutes: int = Field(30, ge=1, le=24 * 60)
    purpose: str | None = Field(None, max_length=80)


class TransferAction(BaseModel):
    clinician_ack: bool = False
    note: str | None = Field(None, max_length=300)


class ManualTransferIn(BaseModel):
    from_facility_id: int
    to_facility_id: int
    abo_rh: AboRh
    component: Component
    quantity: int = Field(ge=1, le=100)
    reason: str | None = Field(None, max_length=300)


class PlanIn(BaseModel):
    region_id: int | None = None
    include_substitutes: bool = True


class IncidentIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    casualties: int = Field(ge=1, le=2000)
    hours: int = Field(12, ge=1, le=72)
    severity_mix: dict[str, float] | None = None  # {"critical":0.2,"serious":0.3,"minor":0.5}
    radius_km: float = Field(25, ge=1, le=200)


class CopilotIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "hi"] = "en"
    history: list[dict] = Field(default_factory=list, max_length=20)


class CampaignIn(BaseModel):
    facility_id: int
    abo_rh: AboRh
    component: Component = "RBC"
    radius_km: float = Field(15, ge=1, le=100)
    language: Literal["en", "hi"] = "hi"
    max_donors: int = Field(50, ge=1, le=500)


class AlertAck(BaseModel):
    note: str | None = Field(None, max_length=300)


class RegisterCommitIn(BaseModel):
    facility_id: int
    rows: list[dict] = Field(max_length=200)

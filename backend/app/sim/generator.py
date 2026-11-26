"""Synthetic ground truth for the demo network (documented in docs/DATA_CARD.md).

One state (Delhi NCT), 4 districts, 31 facilities at realistic coordinates. Demand per
facility x group x component x day comes from an explicit, reproducible process, so forecasts and
alerts can be scored honestly against the truth (replay simulator).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from app.domain.rules import ABO_RH, COMPONENTS, GROUP_MIX
from app.ml.calendar import dengue_index, festival_proximity, static_festivals

SEED = 42

REGIONS = [
    # id, code, name, parent, level, lat, lng
    (1, "STATE", "Delhi NCT", None, "state", 28.6139, 77.2090),
    (2, "ND", "New Delhi", 1, "district", 28.6139, 77.2090),
    (3, "SD", "South Delhi", 1, "district", 28.5244, 77.1855),
    (4, "NDL", "North Delhi", 1, "district", 28.7041, 77.1025),
    (5, "ED", "East Delhi", 1, "district", 28.6280, 77.2950),
]

# code, name, type, subtype, region_id, lat, lng, beds, component_sep, trauma
FACILITIES = [
    ("LH-01", "Sanjeevani General Hospital", "hospital", "large", 2, 28.5672, 77.2100, 900, True, False),
    ("LH-02", "Dhanvantari Medical College Hospital", "hospital", "large", 2, 28.6353, 77.2250, 1200, True, False),
    ("LH-03", "Arogya Multispeciality Hospital", "hospital", "large", 3, 28.5280, 77.2190, 650, True, False),
    ("LH-04", "Jeevan Rekha Institute", "hospital", "large", 3, 28.5450, 77.2730, 700, True, False),
    ("LH-05", "Sushruta City Hospital", "hospital", "large", 4, 28.7160, 77.1700, 800, True, False),
    ("LH-06", "Charaka Memorial Hospital", "hospital", "large", 4, 28.6820, 77.2080, 600, True, False),
    ("LH-07", "Yamuna Paar General Hospital", "hospital", "large", 5, 28.6720, 77.3080, 750, True, False),
    ("LH-08", "Prakash Super Speciality", "hospital", "large", 5, 28.6290, 77.2780, 550, True, False),
    ("SH-01", "Seva Nursing Home", "hospital", "small", 2, 28.5980, 77.1900, 80, False, False),
    ("SH-02", "Ashirwad Clinic & Hospital", "hospital", "small", 2, 28.6450, 77.1900, 60, False, False),
    ("SH-03", "Lotus Community Hospital", "hospital", "small", 3, 28.5000, 77.1700, 90, False, False),
    ("SH-04", "Kalyan Hospital", "hospital", "small", 3, 28.5600, 77.2400, 70, False, False),
    ("SH-05", "Nirmal Health Centre", "hospital", "small", 3, 28.4950, 77.2900, 50, False, False),
    ("SH-06", "Shanti Hospital", "hospital", "small", 4, 28.7350, 77.1150, 75, False, False),
    ("SH-07", "Vardaan Hospital", "hospital", "small", 4, 28.7000, 77.1400, 65, False, False),
    ("SH-08", "Gyan Ganga Hospital", "hospital", "small", 4, 28.7500, 77.1900, 55, False, False),
    ("SH-09", "Pragati Hospital", "hospital", "small", 5, 28.6500, 77.3150, 85, False, False),
    ("SH-10", "Sahyog Nursing Home", "hospital", "small", 5, 28.6100, 77.3000, 45, False, False),
    ("SH-11", "Udaan Hospital", "hospital", "small", 5, 28.6900, 77.2900, 60, False, False),
    ("SH-12", "Mangalam Hospital", "hospital", "small", 2, 28.6200, 77.1650, 70, False, False),
    ("SH-13", "Navjeevan Hospital (new)", "hospital", "small", 5, 28.6000, 77.3300, 60, False, False),
    ("TC-01", "Ring Road Trauma Centre", "hospital", "trauma", 4, 28.6950, 77.2150, 300, True, True),
    ("TC-02", "Highway Trauma Centre", "hospital", "trauma", 3, 28.5350, 77.1500, 250, True, True),
    ("MC-01", "Matritva Maternity Hospital", "hospital", "maternity", 2, 28.6250, 77.2050, 200, True, False),
    ("MC-02", "Janani Women's Hospital", "hospital", "maternity", 5, 28.6600, 77.2700, 180, True, False),
    ("BB-01", "Delhi Central Blood Bank", "blood_bank", "bank", 2, 28.6300, 77.2150, 0, True, False),
    ("BB-02", "South Regional Blood Centre", "blood_bank", "bank", 3, 28.5400, 77.2000, 0, True, False),
    ("BB-03", "North Regional Blood Centre", "blood_bank", "bank", 4, 28.7100, 77.1550, 0, True, False),
    ("BB-04", "East Regional Blood Centre", "blood_bank", "bank", 5, 28.6450, 77.2900, 0, True, False),
    ("BB-05", "Rotary Voluntary Blood Bank", "blood_bank", "bank", 3, 28.5550, 77.2500, 0, True, False),
    ("BB-06", "Red Drop Community Blood Bank", "blood_bank", "bank", 4, 28.6700, 77.1300, 0, True, False),
]

# Daily RBC demand (all groups) by subtype, emergency share, weekday sensitivity.
BASE_RBC = {"large": (16, 26), "small": (2.0, 5.0), "trauma": (12, 16), "maternity": (5, 7), "bank": (2, 4)}
EMERGENCY_SHARE = {"large": 0.35, "small": 0.2, "trauma": 0.75, "maternity": 0.45, "bank": 0.1}
COMP_MULT = {"RBC": 1.0, "PLT": 0.35, "FFP": 0.28, "CRYO": 0.05}
DISPERSION = 3.0  # NB size parameter (lower = burstier)

# Silent periods: (facility code, days-ago start, length in days). Messiness on purpose.
SILENT = [("SH-04", 2, 2), ("SH-08", 60, 6), ("BB-05", 30, 4)]
NEW_FACILITY = "SH-13"
# Mass-casualty / outbreak days in history: (days ago, region_id, multiplier)
INCIDENTS = [(200, 4, 3.0), (95, 3, 2.5), (41, 5, 2.2)]
THAL_SITES = {"LH-02": 40, "LH-05": 30, "BB-01": 50, "LH-07": 25}  # patients per cohort


@dataclass(frozen=True)
class FacilitySpec:
    code: str
    name: str
    type: str
    subtype: str
    region_id: int
    lat: float
    lng: float
    beds: int
    component_sep: bool
    trauma: bool


def facilities() -> list[FacilitySpec]:
    return [FacilitySpec(*f) for f in FACILITIES]


def facility_scale(code: str) -> float:
    """Deterministic per-facility size factor inside the subtype range."""
    rng = np.random.default_rng(sum(ord(ch) * (i + 1) for i, ch in enumerate(code)) * 7919)
    return float(rng.uniform(0, 1))


def base_rbc(f: FacilitySpec) -> float:
    lo, hi = BASE_RBC[f.subtype]
    return lo + (hi - lo) * facility_scale(f.code)


def weekday_factor(f: FacilitySpec, d: date) -> float:
    wd = d.weekday()
    if f.subtype == "trauma":
        return 1.15 if wd >= 5 else 0.95
    return (1.12, 1.12, 1.1, 1.1, 1.05, 0.85, 0.66)[wd]


def demand_rate(f: FacilitySpec, group: str, comp: str, d: date, festivals: dict, incidents_by_day: dict) -> tuple[float, bool]:
    """Expected statistical (non-scheduled) units for one day; returns (lambda, is_event_day)."""
    share = GROUP_MIX[group]
    if group == "O-" and comp == "RBC":
        # O- is released un-crossmatched in emergencies, so usage far exceeds its population share.
        share += EMERGENCY_SHARE[f.subtype] * 0.05
    lam = base_rbc(f) * share * COMP_MULT[comp]
    lam *= weekday_factor(f, d)
    doy = d.timetuple().tm_yday
    lam *= 1 + 0.08 * math.sin(2 * math.pi * (doy - 80) / 365.25)
    fest, _ = festival_proximity(d, festivals)
    if fest:
        lam *= 1 + EMERGENCY_SHARE[f.subtype] * 0.9 * fest
    if comp == "PLT":
        lam *= 1 + 2.2 * dengue_index(d)
    event = False
    inc = incidents_by_day.get(d)
    if inc and inc[0] == f.region_id and f.subtype in ("large", "trauma"):
        lam *= inc[1]
        event = True
    return lam, event


def thal_schedule(today: date, history_days: int, future_days: int, rng: np.random.Generator) -> dict[tuple[str, str], dict[date, int]]:
    """Thalassemia cohorts: each patient gets 2 RBC units every 21 days (no patient identity stored)."""
    out: dict[tuple[str, str], dict[date, int]] = {}
    start = today - timedelta(days=history_days)
    for code, n in THAL_SITES.items():
        for _ in range(n):
            g = rng.choice(ABO_RH, p=[GROUP_MIX[x] for x in ABO_RH])
            phase = int(rng.integers(0, 21))
            d = start + timedelta(days=phase)
            while d < today + timedelta(days=future_days):
                key = (code, str(g))
                out.setdefault(key, {})
                out[key][d] = out[key].get(d, 0) + 2
                d += timedelta(days=21)
    return out


def sample_nb(rng: np.random.Generator, lam: float, size: float = DISPERSION) -> int:
    if lam <= 0:
        return 0
    p = size / (size + lam)
    return int(rng.negative_binomial(size, p))


def incidents_by_day(today: date) -> dict[date, tuple[int, float]]:
    out = {}
    for ago, region, mult in INCIDENTS:
        d0 = today - timedelta(days=ago)
        out[d0] = (region, mult)
        out[d0 + timedelta(days=1)] = (region, 1 + (mult - 1) * 0.5)
    return out


def generate_history(today: date, days: int = 365, seed: int = SEED):
    """Yields (facility_code, date, group, comp, issued, emergency, scheduled, event, quality)."""
    rng = np.random.default_rng(seed)
    fests = static_festivals()
    inc = incidents_by_day(today)
    thal = thal_schedule(today, days, 30, np.random.default_rng(seed + 1))
    silent_days = {(c, today - timedelta(days=a - k)) for c, a, n in SILENT for k in range(n)}
    rows = []
    for f in facilities():
        for i in range(days, 0, -1):
            d = today - timedelta(days=i)
            if f.code == NEW_FACILITY or (f.code, d) in silent_days:
                continue  # missing, not zero
            for g in ABO_RH:
                for c in COMPONENTS:
                    lam, event = demand_rate(f, g, c, d, fests, inc)
                    n = sample_nb(rng, lam)
                    sched = thal.get((f.code, g), {}).get(d, 0) if c == "RBC" else 0
                    emerg = int(rng.binomial(n, EMERGENCY_SHARE[f.subtype])) if n else 0
                    quality = "late" if rng.random() < 0.02 else "ok"
                    rows.append((f.code, d, g, c, n + sched, emerg, sched, event, quality))
    return rows, thal

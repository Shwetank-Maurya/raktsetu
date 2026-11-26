"""Default clinical configuration. These seed the compat_rules / shelf_life_rules tables, which are
the runtime source of truth. Values follow common transfusion practice and MUST be confirmed
against local guidelines (India: NACO / NBTC) before any real use."""

from dataclasses import dataclass

ABO_RH = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")
COMPONENTS = ("RBC", "PLT", "FFP", "CRYO")

# Red cells: donor -> recipients (blueprint A4 table).
RBC_COMPAT: dict[str, tuple[str, ...]] = {
    "O-": ABO_RH,
    "O+": ("O+", "A+", "B+", "AB+"),
    "A-": ("A-", "A+", "AB-", "AB+"),
    "A+": ("A+", "AB+"),
    "B-": ("B-", "B+", "AB-", "AB+"),
    "B+": ("B+", "AB+"),
    "AB-": ("AB-", "AB+"),
    "AB+": ("AB+",),
}

# Plasma ABO rules are reversed (AB plasma is universal); Rh is not relevant for plasma.
_PLASMA_ABO = {"O": ("O",), "A": ("A", "O"), "B": ("B", "O"), "AB": ("AB", "A", "B", "O")}


def _abo(g: str) -> str:
    return g[:-1]


def _plasma_compat(donor: str) -> tuple[str, ...]:
    ok = _PLASMA_ABO[_abo(donor)]
    return tuple(r for r in ABO_RH if _abo(r) in ok)


def _platelet_compat(donor: str) -> tuple[str, ...]:
    # Plasma-compatible ABO preferred; Rh+ platelets are not given to Rh- recipients.
    ok = _plasma_compat(donor)
    if donor.endswith("+"):
        ok = tuple(r for r in ok if r.endswith("+"))
    return ok


def default_compat() -> dict[str, dict[str, tuple[str, ...]]]:
    return {
        "RBC": RBC_COMPAT,
        "FFP": {d: _plasma_compat(d) for d in ABO_RH},
        "CRYO": {d: _plasma_compat(d) for d in ABO_RH},
        "PLT": {d: _platelet_compat(d) for d in ABO_RH},
    }


@dataclass(frozen=True)
class ShelfLife:
    component: str
    shelf_life_hours: float
    min_usable_hours: float  # below this remaining life a unit is not counted as usable stock
    min_life_on_arrival_hours: float  # transfer feasibility
    max_transit_hours: float  # cold-chain limit
    storage: str
    units_per_day_floor: float  # safety-stock floor in units/day of demand


DEFAULT_SHELF_LIFE: dict[str, ShelfLife] = {
    "RBC": ShelfLife("RBC", 42 * 24, 24, 72, 6, "2-6 C", 1.0),
    "PLT": ShelfLife("PLT", 5 * 24, 12, 60, 4, "20-24 C, agitated", 0.5),
    "FFP": ShelfLife("FFP", 365 * 24, 24, 168, 4, "<= -18 C", 0.5),
    "CRYO": ShelfLife("CRYO", 365 * 24, 24, 168, 4, "<= -18 C", 0.2),
}

# Approximate blood-group distribution in North India (sums to 1).
GROUP_MIX: dict[str, float] = {
    "O+": 0.31, "B+": 0.32, "A+": 0.21, "AB+": 0.08,
    "O-": 0.025, "B-": 0.025, "A-": 0.02, "AB-": 0.01,
}

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

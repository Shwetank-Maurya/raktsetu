"""Probabilistic, FEFO-aware time-to-stockout (blueprint B6.2). Pure NumPy, no I/O.

Exact FEFO without simulating every hour per unit
-------------------------------------------------
Sort units by usable-life end e_1 <= ... <= e_n and let D(t) be cumulative demand on a path.
Under FEFO with no backlog, unit k is consumed iff D(e_k) >= c_{k-1} + 1, where c_{k-1} is the
number of earlier units consumed (every earlier unit is gone - used or expired - before unit k
can be touched). The first stockout is the first hour with D(t) > C_n. This is O(n + H) per path
and fully vectorised across paths, so 2,000 paths x ~1,000 series runs in seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.domain.rules import SEVERITY_ORDER

# Share of daily demand per hour (emergency-heavy daytime profile, sums to 1).
HOURLY_PROFILE = np.array(
    [1, 0.8, 0.7, 0.6, 0.6, 0.7, 1.0, 1.5, 2.2, 2.8, 3.0, 3.0,
     2.9, 2.7, 2.6, 2.5, 2.4, 2.2, 2.0, 1.8, 1.6, 1.4, 1.2, 1.1], dtype=float)
HOURLY_PROFILE /= HOURLY_PROFILE.sum()
_SEVERITY_NAME = {v: k for k, v in SEVERITY_ORDER.items()}


@dataclass
class RiskInput:
    usable_hours: list[float]  # remaining usable hours per unit (any order)
    q10: list[float]  # per-day demand quantiles, day 0 = next 24 h
    q50: list[float]
    q90: list[float]
    scheduled: list[float] = field(default_factory=list)  # deterministic units per day (thalassemia, surgery)
    incoming: list[tuple[float, float]] = field(default_factory=list)  # (arrival hour, usable life at arrival)
    lead_time_h: float = 2.0
    demand_multiplier: float = 1.0  # event mode / incident what-if
    start_hour_of_day: int = 0
    mean: list[float] | None = None  # expected daily demand; Swanson's rule from quantiles if None


@dataclass
class RiskResult:
    p_stockout_24: float
    p_stockout_48: float
    p_stockout_72: float
    p_stockout_lead: float
    tts_p10: float | None
    tts_p50: float | None
    expected_wastage: float
    days_cover: float
    mean_daily_demand: float
    usable_units: int
    risk_score: float
    severity: str


def _daily_draws(rng: np.random.Generator, q10: np.ndarray, q50: np.ndarray, q90: np.ndarray, n: int,
                 mean: np.ndarray | None = None) -> np.ndarray:
    """Negative-binomial daily demand matched to the forecast."""
    r, p = nb_params(q10, q50, q90, mean)
    out = rng.negative_binomial(np.broadcast_to(r, (n, len(r))), np.broadcast_to(p, (n, len(p))))
    return out.astype(np.int64)


def expected_demand(q10, q50, q90):
    """Mean from quantiles (Swanson's rule). For skewed, intermittent counts the median can be far
    below the mean (e.g. q50=0.3 when the mean is 0.85); centring on the median under-states risk."""
    return np.maximum(0.3 * np.asarray(q10) + 0.4 * np.asarray(q50) + 0.3 * np.asarray(q90), 0)


def nb_params(q10, q50, q90, mean=None) -> tuple[np.ndarray, np.ndarray]:
    """Negative-binomial (r, p): mean from the forecast's mean model (Swanson's rule if absent),
    variance from the 80% interval width. Shared by the risk engine and the forecast calibration."""
    q10, q50, q90 = (np.asarray(x, dtype=float) for x in (q10, q50, q90))
    mean = np.maximum(np.asarray(mean, dtype=float) if mean is not None else expected_demand(q10, q50, q90), 1e-6)
    sigma = np.maximum((q90 - q10) / 2.563, 0)
    var = np.maximum(sigma**2, mean * 1.05)
    r = mean**2 / (var - mean)
    return r, np.clip(r / (r + mean), 1e-9, 1 - 1e-9)


def _hourly_paths(rng: np.random.Generator, daily: np.ndarray, start_hour: int, hours: int) -> np.ndarray:
    profile = np.roll(HOURLY_PROFILE, -start_hour)
    n, days = daily.shape
    hourly = rng.multinomial(daily.reshape(-1), profile).reshape(n, days * 24)
    return hourly[:, :hours]


def _fefo(cum: np.ndarray, expiry_idx: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Returns (consumed count C_n per path, wasted-within-horizon per path)."""
    n_paths = cum.shape[0]
    consumed = np.zeros(n_paths, dtype=np.int64)
    wasted = np.zeros(n_paths, dtype=np.int64)
    expiry_idx = np.sort(expiry_idx)
    short = expiry_idx[expiry_idx < horizon]
    n_long = int(np.sum(expiry_idx >= horizon))
    for e in short:
        used = cum[:, int(e)] >= consumed + 1
        consumed += used
        wasted += ~used
    if n_long:
        # Units outliving the horizon: all evaluated at the horizon end, so do it in one shot.
        consumed += np.clip(cum[:, horizon - 1] - consumed, 0, n_long)
    return consumed, wasted


def _first_stockout(cum: np.ndarray, consumed: np.ndarray) -> np.ndarray:
    """Hour of first unmet demand per path; np.inf if none within horizon."""
    short = cum > consumed[:, None]
    has = short.any(axis=1)
    first = np.argmax(short, axis=1).astype(float)
    first[~has] = np.inf
    return first


def classify(p24: float, p48: float, p72: float, tts50: float | None, lead: float, scale: float = 1.0) -> str:
    if p24 >= 0.5 * scale or (tts50 is not None and tts50 <= lead):
        return "critical"
    if p48 >= 0.5 * scale or p24 >= 0.2 * scale:
        return "high"
    if p72 >= 0.3 * scale or p48 >= 0.15 * scale:
        return "medium"
    return "low"


def apply_hysteresis(raw_up: str, raw_down: str, previous: str | None) -> str:
    """Escalate immediately; de-escalate only once risk is clearly below the threshold."""
    if previous is None or SEVERITY_ORDER[raw_up] >= SEVERITY_ORDER[previous]:
        return raw_up
    level = max(SEVERITY_ORDER[raw_up], min(SEVERITY_ORDER[previous], SEVERITY_ORDER[raw_down]))
    return _SEVERITY_NAME[level]


def simulate(inp: RiskInput, n_paths: int = 2000, horizon_h: int = 168, seed: int = 0,
             previous_severity: str | None = None) -> RiskResult:
    rng = np.random.default_rng(seed)
    days = int(np.ceil(horizon_h / 24))
    pad = lambda a: np.array((list(a) + [a[-1] if a else 0.0] * days)[:days], dtype=float)  # noqa: E731
    q10, q50, q90 = pad(inp.q10), pad(inp.q50), pad(inp.q90)
    m = max(inp.demand_multiplier, 0.0)
    q10, q50, q90 = q10 * m, q50 * m, q90 * m
    mu = pad(inp.mean) * m if inp.mean else expected_demand(q10, q50, q90)
    sched = pad(inp.scheduled) if inp.scheduled else np.zeros(days)

    daily = _daily_draws(rng, q10, q50, q90, n_paths, mu) + np.round(sched).astype(np.int64)
    hourly = _hourly_paths(rng, daily, inp.start_hour_of_day % 24, horizon_h)
    cum = np.cumsum(hourly, axis=1)

    units = np.sort(np.asarray([h for h in inp.usable_hours if h > 0], dtype=float))
    consumed, wasted = _fefo(cum, np.floor(units).astype(np.int64), horizon_h)
    tts = _first_stockout(cum, consumed)

    if inp.incoming:
        arrivals = np.array([a for a, _ in inp.incoming])
        all_exp = np.sort(np.concatenate([units, np.array([a + life for a, life in inp.incoming])]))
        consumed_all, wasted_all = _fefo(cum, np.floor(all_exp).astype(np.int64), horizon_h)
        tts_all = _first_stockout(cum, consumed_all)
        before = tts < arrivals.min()
        tts = np.where(before, tts, tts_all)
        wasted = np.where(before, wasted, wasted_all)

    p = lambda h: float(np.mean(tts < h))  # noqa: E731
    p24, p48, p72, plead = p(24), p(48), p(72), p(max(inp.lead_time_h, 0.01))
    finite = np.isfinite(tts)
    tts_p10 = float(np.percentile(tts, 10)) if np.mean(finite) > 0.10 else None
    tts_p50 = float(np.percentile(tts, 50)) if np.mean(finite) > 0.50 else None

    mean_daily = float(np.mean(mu + sched))
    usable = int(len(units))
    days_cover = float(usable / mean_daily) if mean_daily > 1e-6 else 999.0

    raw_up = classify(p24, p48, p72, tts_p50, inp.lead_time_h)
    raw_down = classify(p24, p48, p72, tts_p50, inp.lead_time_h, scale=0.7)
    severity = apply_hysteresis(raw_up, raw_down, previous_severity)
    score = 100 * (0.5 * p24 + 0.3 * p48 + 0.2 * p72)
    if severity == "critical":
        score = max(score, 90.0)
    return RiskResult(
        p_stockout_24=round(p24, 4), p_stockout_48=round(p48, 4), p_stockout_72=round(p72, 4),
        p_stockout_lead=round(plead, 4), tts_p10=tts_p10, tts_p50=tts_p50,
        expected_wastage=round(float(np.mean(wasted)), 3), days_cover=round(min(days_cover, 999.0), 2),
        mean_daily_demand=round(mean_daily, 3), usable_units=usable, risk_score=round(min(score, 100.0), 1),
        severity=severity,
    )


def rule_based(usable_units: int, trailing_14d_mean: float, lead_time_h: float) -> RiskResult:
    """Fallback when forecasting fails (edge case #23): days-of-cover thresholds."""
    d = max(trailing_14d_mean, 1e-6)
    cover_h = usable_units / d * 24
    p = lambda h: 1.0 if cover_h < h else (0.5 if cover_h < 1.5 * h else 0.05)  # noqa: E731
    p24, p48, p72 = p(24), p(48), p(72)
    tts = cover_h if cover_h < 168 else None
    sev = classify(p24, p48, p72, tts, lead_time_h)
    return RiskResult(p24, p48, p72, p(lead_time_h), tts, tts, 0.0, round(usable_units / d, 2), round(d, 3),
                      usable_units, round(100 * (0.5 * p24 + 0.3 * p48 + 0.2 * p72), 1), sev)


def confidence(fresh_h: float | None, q10: float, q50: float, q90: float, history_days: int,
               agreement: float = 1.0) -> float:
    """0..1 from data freshness, interval width, history length and model agreement."""
    if fresh_h is None:
        f = 0.3
    else:
        f = 1.0 if fresh_h <= 6 else max(0.3, 1.0 - (fresh_h - 6) / 60)
    width = (q90 - q10) / (q50 + 1.0)
    w = max(0.2, 1.0 - min(1.0, width / 3))
    h = max(0.2, min(1.0, history_days / 90))
    return round(float((f * w * h * max(0.2, agreement)) ** (1 / 4)), 3)

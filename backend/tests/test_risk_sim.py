"""Risk engine: exact FEFO vs a brute-force oracle, monotonicity properties, hysteresis, fallback."""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ml.risk_sim import (
    RiskInput,
    _fefo,
    _first_stockout,
    apply_hysteresis,
    classify,
    confidence,
    rule_based,
    simulate,
)


def brute_force(hourly: np.ndarray, expiries: list[int], horizon: int) -> tuple[int, int, float]:
    """Hour-by-hour FEFO simulation for ONE path: (consumed, wasted, first stockout hour)."""
    stock = sorted(expiries)
    consumed = wasted = 0
    first = np.inf
    for t in range(horizon):
        while stock and stock[0] <= t - 1 + 1 and stock[0] < t:  # expired before hour t
            stock.pop(0)
            wasted += 1
        for _ in range(int(hourly[t])):
            # drop units whose usable life ended before this hour
            while stock and stock[0] < t:
                stock.pop(0)
                wasted += 1
            if stock:
                stock.pop(0)
                consumed += 1
            elif first == np.inf:
                first = t
    wasted += sum(1 for e in stock if e < horizon)
    return consumed, wasted, first


@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(0, 3), min_size=24, max_size=24), st.lists(st.integers(0, 30), max_size=12))
def test_vectorised_fefo_matches_bruteforce(hourly, expiries):
    horizon = 24
    h = np.array([hourly], dtype=np.int64)
    cum = np.cumsum(h, axis=1)
    consumed, wasted = _fefo(cum, np.array(expiries, dtype=np.int64), horizon)
    tts = _first_stockout(cum, consumed)
    bc, bw, bf = brute_force(np.array(hourly), list(expiries), horizon)
    assert consumed[0] == bc
    assert wasted[0] == bw
    assert tts[0] == bf


def _inp(units, q50=3.0, lead=2.0, **kw):
    return RiskInput(usable_hours=units, q10=[q50 * 0.4] * 7, q50=[q50] * 7, q90=[q50 * 1.8] * 7, lead_time_h=lead, **kw)


@settings(max_examples=25, deadline=None)
@given(st.lists(st.floats(1, 300), max_size=15), st.floats(1, 300), st.floats(0.2, 8))
def test_more_stock_never_increases_risk(units, extra, q50):
    a = simulate(_inp(units, q50), n_paths=300, seed=1)
    b = simulate(_inp(units + [extra], q50), n_paths=300, seed=1)
    assert b.p_stockout_24 <= a.p_stockout_24 + 1e-9
    assert b.p_stockout_72 <= a.p_stockout_72 + 1e-9


@settings(max_examples=25, deadline=None)
@given(st.lists(st.floats(1, 300), max_size=15), st.floats(0.1, 20), st.floats(0.1, 20))
def test_longer_lead_never_decreases_risk(units, l1, l2):
    lo, hi = sorted((l1, l2))
    a = simulate(_inp(units, lead=lo), n_paths=300, seed=2)
    b = simulate(_inp(units, lead=hi), n_paths=300, seed=2)
    assert b.p_stockout_lead >= a.p_stockout_lead - 1e-9
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    assert order[b.severity] >= order[a.severity]


def test_zero_demand_zero_risk():
    r = simulate(RiskInput([], [0] * 7, [0] * 7, [0] * 7), n_paths=200)
    assert r.p_stockout_72 == 0 and r.severity == "low"


def test_empty_shelf_with_demand_is_high_or_critical():
    r = simulate(_inp([], q50=4.0), n_paths=500)
    assert r.p_stockout_24 > 0.9 and r.severity == "critical"


def test_expiring_units_are_wasted_not_counted():
    # 10 units that all die in 5 h with tiny demand -> almost all wasted, stockout soon after.
    r = simulate(_inp([5.0] * 10, q50=0.2), n_paths=400)
    assert r.expected_wastage > 8
    assert r.p_stockout_72 > 0.3


def test_incoming_transfer_reduces_risk():
    base = simulate(_inp([10.0], q50=3), n_paths=400, seed=3)
    helped = simulate(_inp([10.0], q50=3, incoming=[(1.0, 400.0)] * 10), n_paths=400, seed=3)
    assert helped.p_stockout_72 < base.p_stockout_72


def test_mean_drives_demand_not_median():
    # intermittent series: median 0, mean 0.9 -> risk must reflect the mean
    lo = simulate(RiskInput([], [0] * 7, [0] * 7, [3] * 7, mean=[0.05] * 7), n_paths=500, seed=4)
    hi = simulate(RiskInput([], [0] * 7, [0] * 7, [3] * 7, mean=[0.9] * 7), n_paths=500, seed=4)
    assert hi.p_stockout_24 > lo.p_stockout_24 + 0.2


def test_hysteresis_holds_then_releases():
    assert apply_hysteresis("medium", "high", "high") == "high"      # small dip: hold
    assert apply_hysteresis("low", "low", "high") == "low"           # clearly calm: release
    assert apply_hysteresis("critical", "critical", "low") == "critical"  # escalate immediately


def test_classify_lead_time_rule():
    # runs out in 14 h with a 10 h transfer: fine; with a 15 h transfer: critical
    assert classify(0.1, 0.2, 0.3, 14.0, 10.0) != "critical"
    assert classify(0.1, 0.2, 0.3, 14.0, 15.0) == "critical"


def test_rule_based_fallback():
    r = rule_based(usable_units=2, trailing_14d_mean=4.0, lead_time_h=2)
    assert r.severity == "critical" and r.days_cover == 0.5


def test_confidence_decays_with_staleness():
    assert confidence(1, 1, 3, 5, 200) > confidence(40, 1, 3, 5, 200) > confidence(None, 1, 3, 5, 200) * 0.9

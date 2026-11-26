"""Clinical rules and the OR-Tools optimizer (pure functions, no DB)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.compat import RuleBook
from app.domain.rules import ABO_RH
from app.optimizer.allocate import Params, SeriesState, plan, safety_stock

BOOK = RuleBook.default()

RBC_TABLE = {  # blueprint A4, verbatim
    "O-": set(ABO_RH), "O+": {"O+", "A+", "B+", "AB+"}, "A-": {"A-", "A+", "AB-", "AB+"}, "A+": {"A+", "AB+"},
    "B-": {"B-", "B+", "AB-", "AB+"}, "B+": {"B+", "AB+"}, "AB-": {"AB-", "AB+"}, "AB+": {"AB+"},
}


@pytest.mark.parametrize("donor", ABO_RH)
@pytest.mark.parametrize("recipient", ABO_RH)
def test_rbc_matrix_matches_blueprint(donor, recipient):
    assert BOOK.can_give("RBC", donor, recipient) == (recipient in RBC_TABLE[donor])


def test_plasma_rules_are_reversed():
    assert all(BOOK.can_give("FFP", "AB+", r) for r in ABO_RH)  # AB plasma is universal
    assert BOOK.can_give("FFP", "O+", "O-") and not BOOK.can_give("FFP", "O+", "A+")


@given(st.sampled_from(ABO_RH))
def test_donor_order_conserves_o_negative(recipient):
    donors = BOOK.donors_for("RBC", recipient)
    assert donors[0] == recipient  # identical group first
    if "O-" in donors and len(donors) > 1:
        assert donors[-1] == "O-"  # universal donor last


def _s(f, g="O+", c="RBC", units=(), q50=2.0, q90=4.0, sev="low", waste=0.0, bank=False, p24=0.0):
    return SeriesState(f, g, c, sorted(units), q50, q90, sev, p24, None, waste, bank)


def _eta(n, minutes=30.0, km=10.0):
    return {(i, j): (minutes, km, "test") for i in range(1, n + 1) for j in range(1, n + 1) if i != j}


def test_deficit_is_covered_from_surplus_with_reason():
    states = {(1, "O+", "RBC"): _s(1, units=[], sev="critical", p24=0.9),
              (2, "O+", "RBC"): _s(2, units=[500] * 30, bank=True)}
    res = plan(states, _eta(2), BOOK)
    assert res.proposals and res.proposals[0].from_facility_id == 2 and res.proposals[0].to_facility_id == 1
    r = res.proposals[0].reason
    assert {"destination", "source", "saves", "constraints"} <= set(r)


@settings(max_examples=20, deadline=None)
@given(st.integers(0, 40), st.floats(0.5, 6))
def test_optimizer_never_breaches_donor_safety_stock(donor_units, q50):
    donor = _s(2, units=[500] * donor_units, q50=q50, q90=q50 * 2)
    states = {(1, "O+", "RBC"): _s(1, units=[], sev="critical", q50=5, p24=1.0), (2, "O+", "RBC"): donor}
    res = plan(states, _eta(2), BOOK)
    sent = sum(p.quantity for p in res.proposals if p.from_facility_id == 2)
    assert donor_units - sent >= min(donor_units, safety_stock(donor, BOOK, Params()))


def test_all_short_returns_partial_plan_and_deficits():
    states = {(f, "O-", "RBC"): _s(f, "O-", units=[300], sev="critical", q50=3, p24=0.9) for f in (1, 2, 3)}
    res = plan(states, _eta(3), BOOK)
    assert res.deficits and all(d["unmet_units"] > 0 for d in res.deficits)


def test_cold_chain_limit_rejects_long_transfers():
    states = {(1, "O+", "RBC"): _s(1, units=[], sev="critical", p24=1), (2, "O+", "RBC"): _s(2, units=[500] * 30, bank=True)}
    res = plan(states, _eta(2, minutes=60 * 7), BOOK)  # 7 h > 6 h RBC cold-chain limit
    assert not res.proposals


def test_platelets_with_short_life_are_not_transferred():
    # 2 days left (48 h) < 60 h minimum life on arrival for platelets
    states = {(1, "O+", "PLT"): _s(1, c="PLT", units=[], sev="critical", p24=1),
              (2, "O+", "PLT"): _s(2, c="PLT", units=[48 - 12] * 20, bank=True)}
    assert not plan(states, _eta(2), BOOK).proposals


def test_plan_is_stable_across_runs():
    states = {(1, "O+", "RBC"): _s(1, units=[], sev="high", p24=0.4), (2, "O+", "RBC"): _s(2, units=[500] * 15, bank=True),
              (3, "O+", "RBC"): _s(3, units=[500] * 15, bank=True)}
    a = plan(states, _eta(3), BOOK)
    b = plan(states, _eta(3), BOOK, stable={(p.from_facility_id, p.to_facility_id, "O+", "RBC") for p in a.proposals})
    key = lambda r: sorted((p.from_facility_id, p.to_facility_id, p.quantity) for p in r.proposals)  # noqa: E731
    assert key(a) == key(b)


def test_at_risk_facility_never_donates():
    states = {(1, "O+", "RBC"): _s(1, units=[], sev="critical", p24=1),
              (2, "O+", "RBC"): _s(2, units=[60] * 5, sev="high", waste=3, p24=0.3)}
    assert all(p.from_facility_id != 2 for p in plan(states, _eta(2), BOOK).proposals)


def test_substitutes_need_clinician_and_conserve_rh_negative():
    states = {(1, "A+", "RBC"): _s(1, "A+", units=[], sev="critical", p24=1, q50=3),
              (2, "O+", "RBC"): _s(2, "O+", units=[500] * 20, bank=True),
              (2, "O-", "RBC"): _s(2, "O-", units=[500] * 20, bank=True)}
    res = plan(states, _eta(2), BOOK)
    subs = [p for p in res.proposals if p.requested_for_abo_rh == "A+"]
    assert subs and all(p.needs_clinician_approval for p in subs)
    assert all(p.abo_rh != "O-" for p in subs)  # O- is not spent on an Rh+ patient


def test_near_expiry_units_are_rescued():
    states = {(1, "O+", "RBC"): _s(1, units=[500] * 2, q50=3, sev="medium", p24=0.1),
              (2, "O+", "RBC"): _s(2, units=[110.0] * 6, q50=0.05, q90=0.2, waste=6, bank=True)}
    res = plan(states, _eta(2, minutes=20), BOOK)
    assert sum(p.reason["saves"]["wastage_units"] for p in res.proposals) > 0


def test_three_hundred_facilities_within_time_budget():
    import time

    n = 300
    states = {}
    for f in range(1, n + 1):
        states[(f, "O+", "RBC")] = _s(f, units=[400] * (0 if f % 10 == 0 else 25), sev="critical" if f % 10 == 0 else "low",
                                      p24=0.9 if f % 10 == 0 else 0)
    eta = {(i, j): (abs(i - j) * 3.0 + 15, abs(i - j) * 1.0, "t") for i in range(1, n + 1) for j in range(1, n + 1)
           if i != j and abs(i - j) <= 8}
    t0 = time.perf_counter()
    res = plan(states, eta, BOOK)
    assert time.perf_counter() - t0 < 20 and res.proposals

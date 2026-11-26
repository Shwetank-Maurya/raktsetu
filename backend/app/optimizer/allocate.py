"""Constraint-aware transfer optimizer (blueprint B6.3) using Google OR-Tools (SCIP MIP).

Per (blood group, component):
  minimise  sum_j W_j * unmet_j                    (severity-weighted shortage)
          + a * sum_ij eta_ij * x_ij               (transport time)
          + b * sum_ij y_ij                        (fixed cost per transfer -> few, larger moves)
          - g * sum_ij r_ij                        (rescue bonus: near-expiry units that get used)
          - d * sum_ij stable_ij * y_ij            (stability: keep previous proposals)
  s.t.  sum_j x_ij <= avail_i                     (supply above donor safety stock + doomed units)
        x_ij <= feasible_ij * y_ij                (only units with enough life on arrival; ETA <= cold-chain limit)
        sum_i x_ij + unmet_j >= deficit_j
        sum_i x_ij <= deficit_j + absorb_j        (never ship more than the destination can use)
        r_ij <= x_ij, sum_j r_ij <= waste_i, sum_i r_ij <= absorb_j + deficit_j
        sum_j y_ij <= max_out, sum_i y_ij <= max_in
A greedy second pass proposes compatible substitutions for any remaining unmet demand, always
flagged needs_clinician_approval. Pure function: no I/O, deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ortools.linear_solver import pywraplp

from app.domain.compat import RuleBook

SEV_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 4.0}


@dataclass
class SeriesState:
    facility_id: int
    abo_rh: str
    component: str
    usable_hours: list[float]  # sorted remaining usable hours per unit
    daily_q50: float
    daily_q90: float
    severity: str = "low"
    p24: float = 0.0
    tts_p50: float | None = None
    expected_wastage: float = 0.0
    is_bank: bool = False


@dataclass
class Params:
    horizon_days: float = 3.0
    k_nearest: int = 6
    radius_km: float = 60.0
    max_out: int = 3
    max_in: int = 3
    time_limit_s: float = 5.0
    min_bank_floor: int = 2
    a_eta: float = 0.02
    b_fixed: float = 15.0
    g_rescue: float = 40.0
    d_stable: float = 3.0
    w_unmet: float = 1000.0


@dataclass
class Proposal:
    from_facility_id: int
    to_facility_id: int
    abo_rh: str
    component: str
    quantity: int
    eta_minutes: float
    distance_km: float
    eta_source: str
    min_life_on_arrival_h: float
    kind: str
    needs_clinician_approval: bool = False
    requested_for_abo_rh: str | None = None
    reason: dict = field(default_factory=dict)


@dataclass
class PlanResult:
    proposals: list[Proposal]
    deficits: list[dict]  # remaining unmet need after both passes (regional deficit)
    stats: dict


def safety_stock(s: SeriesState, book: RuleBook, p: Params) -> int:
    """Donor never drops below max(own P90 need over the planning horizon, configured floor)."""
    floor = book.shelf[s.component].units_per_day_floor * 2
    if s.is_bank:
        return max(p.min_bank_floor, math.ceil(s.daily_q90))
    return max(math.ceil(s.daily_q90 * p.horizon_days), math.ceil(floor))


def deficit(s: SeriesState, p: Params) -> int:
    if s.is_bank or SEV_WEIGHT[s.severity] < 2:
        return 0  # only medium+ risk facilities ask for help
    mu = max(s.daily_q50, 0) * p.horizon_days
    need = mu + math.sqrt(mu)  # median need over the horizon + ~1 sd buffer
    return max(0, math.ceil(need - 1e-9) - len(s.usable_hours))


def absorb_capacity(s: SeriesState, life_days: float) -> int:
    """Units the destination can actually use before a near-expiry unit dies."""
    if s.is_bank:
        return 0
    return max(0, int(s.daily_q50 * life_days) - len(s.usable_hours))


def _feasible_count(s: SeriesState, eta_h: float, min_life_h: float) -> int:
    return sum(1 for h in s.usable_hours if h >= eta_h + min_life_h)


def solve_group(
    states: dict[int, SeriesState], eta: dict[tuple[int, int], tuple[float, float, str]], book: RuleBook,
    p: Params, stable: set[tuple[int, int]] | None = None,
) -> tuple[list[Proposal], dict[int, int], dict[int, int]]:
    """Solve one (group, component). Returns proposals, leftover avail per source, unmet per sink."""
    stable = stable or set()
    if not states:
        return [], {}, {}
    any_s = next(iter(states.values()))
    g, c = any_s.abo_rh, any_s.component
    shelf = book.shelf[c]
    avail: dict[int, int] = {}
    waste: dict[int, int] = {}
    need = {f: deficit(s, p) for f, s in states.items()}
    for f, s in states.items():
        if need[f] > 0 or SEV_WEIGHT[s.severity] >= 3:
            avail[f], waste[f] = 0, 0  # a facility that is itself at risk never donates (no ping-pong)
            continue
        surplus = max(0, len(s.usable_hours) - safety_stock(s, book, p))
        doomed = min(len(s.usable_hours), int(round(s.expected_wastage)))
        avail[f] = min(len(s.usable_hours), surplus + doomed)
        waste[f] = doomed
    absorb = {f: absorb_capacity(s, 2.0 if c == "PLT" else 7.0) for f, s in states.items()}

    sources = [f for f in states if avail[f] > 0]
    sinks = [f for f in states if need[f] > 0 or (absorb[f] > 0 and any(waste.values()))]
    pairs: dict[tuple[int, int], int] = {}
    for j in sinks:
        cands = []
        for i in sources:
            if i == j or (i, j) not in eta:
                continue
            minutes, km, _ = eta[(i, j)]
            if km > p.radius_km or minutes / 60 > shelf.max_transit_hours:
                continue
            feas = min(avail[i], _feasible_count(states[i], minutes / 60, shelf.min_life_on_arrival_hours))
            if feas > 0:
                cands.append((minutes, i, feas))
        for _minutes, i, feas in sorted(cands)[: p.k_nearest]:
            pairs[(i, j)] = feas
    if not pairs:
        return [], avail, {j: need[j] for j in sinks if need[j] > 0}

    solver = pywraplp.Solver.CreateSolver("SCIP") or pywraplp.Solver.CreateSolver("CBC")
    solver.SetTimeLimit(int(p.time_limit_s * 1000))
    x = {k: solver.IntVar(0, v, f"x_{k[0]}_{k[1]}") for k, v in pairs.items()}
    y = {k: solver.BoolVar(f"y_{k[0]}_{k[1]}") for k in pairs}
    r = {k: solver.NumVar(0, solver.infinity(), f"r_{k[0]}_{k[1]}") for k in pairs}
    unmet = {j: solver.NumVar(0, need[j], f"u_{j}") for j in sinks}

    for i in sources:
        out_pairs = [k for k in pairs if k[0] == i]
        if out_pairs:
            solver.Add(sum(x[k] for k in out_pairs) <= avail[i])
            solver.Add(sum(y[k] for k in out_pairs) <= p.max_out)
            solver.Add(sum(r[k] for k in out_pairs) <= waste[i])
    for k, v in pairs.items():
        solver.Add(x[k] <= v * y[k])
        solver.Add(r[k] <= x[k])
        # Routine (medium) needs are not worth a courier for a single unit; urgent ones are.
        min_q = 1 if (SEV_WEIGHT[states[k[1]].severity] >= 3 or need[k[1]] < 2) else min(2, v)
        solver.Add(x[k] >= min_q * y[k])
    for j in sinks:
        in_pairs = [k for k in pairs if k[1] == j]
        solver.Add(sum(x[k] for k in in_pairs) + unmet[j] >= need[j])
        solver.Add(sum(x[k] for k in in_pairs) <= need[j] + absorb[j])
        solver.Add(sum(r[k] for k in in_pairs) <= need[j] + absorb[j])
        if in_pairs:
            solver.Add(sum(y[k] for k in in_pairs) <= p.max_in)

    obj = solver.Objective()
    for j in sinks:
        obj.SetCoefficient(unmet[j], p.w_unmet * SEV_WEIGHT[states[j].severity])
    for k in pairs:
        obj.SetCoefficient(x[k], p.a_eta * eta[k][0])
        obj.SetCoefficient(y[k], p.b_fixed - (p.d_stable if k in stable else 0.0))
        obj.SetCoefficient(r[k], -p.g_rescue)
    obj.SetMinimization()
    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return [], avail, {j: need[j] for j in sinks if need[j] > 0}

    proposals: list[Proposal] = []
    left = dict(avail)
    for k in sorted(pairs, key=lambda k: (k[1], eta[k][0])):
        q = int(round(x[k].solution_value()))
        if q <= 0:
            continue
        i, j = k
        rescued = int(round(r[k].solution_value()))
        minutes, km, src = eta[k]
        left[i] -= q
        si, sj = states[i], states[j]
        life_arrival = [h - minutes / 60 for h in si.usable_hours if h >= minutes / 60 + shelf.min_life_on_arrival_hours][:q]
        alts = sorted((eta[a][0], a[0]) for a in pairs if a[1] == j and a[0] != i)[:2]
        proposals.append(Proposal(
            from_facility_id=i, to_facility_id=j, abo_rh=g, component=c, quantity=q,
            eta_minutes=round(minutes, 1), distance_km=round(km, 2), eta_source=src,
            min_life_on_arrival_h=round(min(life_arrival) if life_arrival else shelf.min_life_on_arrival_hours, 1),
            kind="rescue" if rescued >= q and need[j] == 0 else "deficit",
            reason={
                "objective": "severity-weighted shortage + transport time - rescue of near-expiry units",
                "destination": {"severity": sj.severity, "p_stockout_24h": sj.p24, "tts_p50_h": sj.tts_p50,
                                "usable_before": len(sj.usable_hours), "need_units": need[j]},
                "source": {"usable_before": len(si.usable_hours), "safety_stock": safety_stock(si, book, p),
                           "usable_after": len(si.usable_hours) - q, "expected_wastage": si.expected_wastage},
                "saves": {"shortage_units": max(0, min(q, need[j])), "wastage_units": rescued},
                "constraints": {"eta_min": round(minutes, 1), "max_transit_h": shelf.max_transit_hours,
                                "min_life_on_arrival_h": shelf.min_life_on_arrival_hours,
                                "life_on_arrival_h": round(min(life_arrival), 1) if life_arrival else None,
                                "eta_source": src},
                "alternatives": [{"facility_id": a, "eta_min": round(m, 1)} for m, a in alts],
                "stable": k in stable,
            },
        ))
    rem = {j: int(math.ceil(unmet[j].solution_value() - 1e-6)) for j in sinks}
    return proposals, left, {j: v for j, v in rem.items() if v > 0}


def substitution_pass(
    unmet: dict[tuple[int, str, str], int], leftovers: dict[tuple[int, str, str], int],
    states: dict[tuple[int, str, str], SeriesState], eta: dict[tuple[int, int], tuple[float, float, str]],
    book: RuleBook, p: Params,
) -> tuple[list[Proposal], dict[tuple[int, str, str], int]]:
    """Greedy compatible substitutes for what the primary pass could not cover. Never automatic:
    every proposal needs clinician approval. O- is only used for Rh-negative recipients."""
    props: list[Proposal] = []
    remaining = dict(unmet)
    # Substitutes only for high/critical needs: a clinician should not be paged for a medium risk.
    order = sorted((k for k in unmet if k in states and SEV_WEIGHT[states[k].severity] >= 3),
                   key=lambda k: -SEV_WEIGHT[states[k].severity])
    for (j, g, c) in order:
        shelf = book.shelf[c]
        used_sources = 0
        for donor in book.donors_for(c, g):
            # Rh-negative stock is conserved for Rh-negative patients (includes O-, the universal donor).
            if donor == g or (donor.endswith("-") and g.endswith("+")):
                continue
            cands = []
            for (i, dg, dc), left in leftovers.items():
                if dg != donor or dc != c or left <= 0 or i == j or (i, j) not in eta:
                    continue
                minutes, km, _ = eta[(i, j)]
                if km > p.radius_km or minutes / 60 > shelf.max_transit_hours:
                    continue
                st = states.get((i, dg, dc))
                feas = min(left, _feasible_count(st, minutes / 60, shelf.min_life_on_arrival_hours)) if st else 0
                if feas > 0:
                    cands.append((minutes, i, feas))
            # Prefer few, large sources (fewer couriers), then the closest.
            for minutes, i, feas in sorted(cands, key=lambda x: (-x[2], x[0])):
                if remaining[(j, g, c)] <= 0 or used_sources >= p.max_in:
                    break
                used_sources += 1
                q = min(feas, remaining[(j, g, c)])
                remaining[(j, g, c)] -= q
                leftovers[(i, donor, c)] -= q
                _, km, src = eta[(i, j)]
                props.append(Proposal(
                    from_facility_id=i, to_facility_id=j, abo_rh=donor, component=c, quantity=q,
                    eta_minutes=round(minutes, 1), distance_km=round(km, 2), eta_source=src,
                    min_life_on_arrival_h=shelf.min_life_on_arrival_hours, kind="deficit",
                    needs_clinician_approval=True, requested_for_abo_rh=g,
                    reason={"substitution": f"{donor} {c} for {g} recipient",
                            "warning": "Compatible substitute. Requires clinician sign-off before approval.",
                            "destination": {"severity": states[(j, g, c)].severity if (j, g, c) in states else None},
                            "saves": {"shortage_units": q, "wastage_units": 0},
                            "constraints": {"eta_min": round(minutes, 1), "eta_source": src}},
                ))
            if remaining[(j, g, c)] <= 0:
                break
    return props, {k: v for k, v in remaining.items() if v > 0}


def plan(
    states: dict[tuple[int, str, str], SeriesState], eta: dict[tuple[int, int], tuple[float, float, str]],
    book: RuleBook, params: Params | None = None, stable: set[tuple[int, int, str, str]] | None = None,
    include_substitutes: bool = True,
) -> PlanResult:
    p = params or Params()
    stable = stable or set()
    by_group: dict[tuple[str, str], dict[int, SeriesState]] = {}
    for (f, g, c), s in states.items():
        by_group.setdefault((g, c), {})[f] = s
    proposals: list[Proposal] = []
    leftovers: dict[tuple[int, str, str], int] = {}
    unmet: dict[tuple[int, str, str], int] = {}
    for (g, c), group_states in sorted(by_group.items()):
        st = {(i, j) for (i, j, sg, sc) in stable if sg == g and sc == c}
        props, left, um = solve_group(group_states, eta, book, p, st)
        proposals += props
        for f, v in left.items():
            leftovers[(f, g, c)] = v
        for f, v in um.items():
            unmet[(f, g, c)] = v
    subs: list[Proposal] = []
    if include_substitutes and unmet:
        subs, unmet = substitution_pass(unmet, leftovers, states, eta, book, p)
    deficits = [{"facility_id": f, "abo_rh": g, "component": c, "unmet_units": v,
                 "severity": states[(f, g, c)].severity if (f, g, c) in states else "high"}
                for (f, g, c), v in sorted(unmet.items())]
    return PlanResult(proposals + subs, deficits, {
        "groups_solved": len(by_group), "proposals": len(proposals), "substitutions": len(subs),
        "unmet_units": sum(unmet.values()),
        "rescued_units": sum(pp.reason.get("saves", {}).get("wastage_units", 0) for pp in proposals),
    })

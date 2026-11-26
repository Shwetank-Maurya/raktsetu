"""Closed-loop replay simulator (blueprint D2). Usage: python -m scripts.replay_sim [--days 90]

Replays N days of the synthetic ground-truth demand twice with COMMON RANDOM NUMBERS (identical
demand, donations and starting stock for both policies):

  Policy A - static: each hospital orders from its district blood bank when a series falls below a
             fixed threshold ("alert at N units"), ordering up to 2x the threshold. No lateral moves.
  Policy B - RaktSetu: forecast-driven order-up-to levels (exponentially smoothed demand + safety
             stock from observed variability, shorter targets for 5-day platelets), probabilistic
             48 h stockout warnings, emergency lateral transfers from facilities with surplus above
             their own safety stock, and use-it-or-move-it moves of near-expiry units to the
             facility most likely to use them before expiry.

Reports wastage, unmet units, stockout series-days, fulfilment, and 48 h-ahead alert recall and
precision for both. This is a simplified daily model of the live system (documented in
docs/EVALUATION.md); it is evidence of direction and rough magnitude, not a clinical claim.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.calendar import static_festivals  # noqa: E402
from app.optimizer.routes import haversine_km  # noqa: E402
from app.services.forecasting import today_ist  # noqa: E402
from app.sim import generator as G  # noqa: E402

COMPS = {"RBC": 42, "PLT": 5}  # shelf life in days
GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]
STATIC_THRESHOLD = {"large": 10, "trauma": 8, "maternity": 5, "small": 3}  # units, per group x component


def nb_sf(k: int, mu: float, size: float = 3.0) -> float:
    """P(X > k) for an over-dispersed negative binomial (mean mu, size r): demand is bursty, and a
    Poisson tail would call the very bursts that cause stockouts near-impossible."""
    if mu <= 0:
        return 0.0
    p = size / (size + mu)
    term = cdf = p**size
    for i in range(1, k + 1):
        term *= (i - 1 + size) / i * (1 - p)
        cdf += term
    return max(0.0, 1 - cdf)


def run(policy: str, days: int, seed: int = 7) -> dict:
    rng_d = np.random.default_rng(seed)        # demand stream (shared)
    rng_s = np.random.default_rng(seed + 1)    # supply stream (shared)
    rng_i = np.random.default_rng(seed + 2)    # initial stock (shared)
    today = today_ist()
    start = today - timedelta(days=days)
    fests, inc = static_festivals(), G.incidents_by_day(today)
    specs = G.facilities()
    hosp = [f for f in specs if f.type == "hospital"]
    banks = [f for f in specs if f.type == "blood_bank"]
    home_bank = {f.code: min((b for b in banks if b.region_id == f.region_id) or banks,
                             key=lambda b: haversine_km((f.lat, f.lng), (b.lat, b.lng))) for f in hosp}
    stock: dict[tuple, list[float]] = {}
    est: dict[tuple, float] = {}
    var: dict[tuple, float] = {}
    for f in specs:
        for g in GROUPS:
            for c, life in COMPS.items():
                lam = G.demand_rate(f, g, c, start, fests, inc)[0]
                k = (f.code, g, c)
                cover = (5 if c == "RBC" else 2.5) if f.type == "hospital" else 0
                n = int(round(lam * cover))
                stock[k] = sorted(rng_i.uniform(1, life, size=n).tolist())
                est[k], var[k] = lam, lam
    for b in banks:
        for g in GROUPS:
            for c, life in COMPS.items():
                tot = sum(G.demand_rate(h, g, c, start, fests, inc)[0] for h in hosp if home_bank[h.code] == b)
                stock[(b.code, g, c)] = sorted(rng_i.uniform(1, life, size=int(round(tot * 2))).tolist())

    m = {"wasted": 0, "unmet": 0, "demand": 0, "stockout_days": 0, "transfers": 0, "lateral_units": 0,
         "alerts": 0, "alerts_true": 0, "stockouts_warned": 0}
    alert_log: dict[tuple, list[int]] = {}
    stockout_log: list[tuple[tuple, int]] = []

    def take(k_from, n, min_life=0.0):
        s = stock[k_from]
        usable = [x for x in s if x >= min_life]
        moved = usable[:n]
        for x in moved:
            s.remove(x)
        return moved

    def give(k_to, units):
        stock[k_to] = sorted(stock[k_to] + units)

    for day in range(days):
        d = start + timedelta(days=day)
        # 1) donations arrive at blood banks (~2% above network demand)
        for b in banks:
            for g in GROUPS:
                for c, life in COMPS.items():
                    tot = sum(G.demand_rate(h, g, c, d, fests, inc)[0] for h in hosp if home_bank[h.code] == b)
                    give((b.code, g, c), [float(life)] * int(rng_s.poisson(tot * 1.02)))
        # 2) replenishment + warnings
        for h in hosp:
            for g in GROUPS:
                for c in COMPS:
                    k, kb = (h.code, g, c), (home_bank[h.code].code, g, c)
                    have = len(stock[k])
                    if policy == "A":
                        thr = STATIC_THRESHOLD[h.subtype] if (g.endswith("+") or h.subtype != "small") else 1
                        thr = max(1, int(thr * (0.5 if c == "PLT" else 1) * (0.3 if g.endswith("-") else 1)))
                        if have < thr:
                            m["alerts"] += 1
                            alert_log.setdefault(k, []).append(day)
                            give(k, take(kb, 2 * thr - have, min_life=1))
                            m["transfers"] += 1
                    else:
                        mu = est[k]
                        sd = math.sqrt(max(var[k], mu))
                        cover_days = 2.0 if c == "PLT" else 3.0
                        target = math.ceil(mu * cover_days + 1.28 * sd * math.sqrt(cover_days))
                        if have < target:
                            got = take(kb, target - have, min_life=2 if c == "PLT" else 3)
                            if len(got) < target - have:  # bank short: lateral transfer from surplus peers
                                need = target - have - len(got)
                                for p in sorted(hosp, key=lambda p: haversine_km((h.lat, h.lng), (p.lat, p.lng))):
                                    kp = (p.code, g, c)
                                    if p.code == h.code or need <= 0:
                                        continue
                                    spare = len(stock[kp]) - math.ceil(est[kp] * cover_days * 1.3)
                                    if spare > 0:
                                        mv = take(kp, min(spare, need), min_life=2 if c == "PLT" else 3)
                                        need -= len(mv)
                                        got += mv
                                        m["lateral_units"] += len(mv)
                            give(k, got)
                            m["transfers"] += 1
                        # Warning after resupply: P(stockout within 48 h) >= 0.25 (live 'high' tier band)
                        if nb_sf(len(stock[k]), 2 * mu, size=6.0) >= 0.25:
                            m["alerts"] += 1
                            alert_log.setdefault(k, []).append(day)
        # 3) use-it-or-move-it (policy B): units that will expire before local demand reaches them
        if policy == "B":
            for c in COMPS:
                for g in GROUPS:
                    for f in specs:
                        k = (f.code, g, c)
                        rate = est.get(k, 0.0) if f.type == "hospital" else 0.0
                        doomed = [x for i, x in enumerate(stock[k]) if x <= 3 and i + 1 > rate * x]
                        if not doomed:
                            continue
                        best = max((h for h in hosp if h.code != f.code), key=lambda h: est[(h.code, g, c)] /
                                   (1 + len(stock[(h.code, g, c)])) - haversine_km((f.lat, f.lng), (h.lat, h.lng)) / 200)
                        kb = (best.code, g, c)
                        can_use = int(est[kb] * min(doomed)) - len([x for x in stock[kb] if x <= min(doomed)])
                        if can_use > 0:
                            mv = doomed[:can_use]
                            for x in mv:
                                stock[k].remove(x)
                            give(kb, mv)
                            m["lateral_units"] += len(mv)
                            m["transfers"] += 1
        # 4) demand (FEFO), then ageing and expiry
        for h in specs:
            for g in GROUPS:
                for c in COMPS:
                    k = (h.code, g, c)
                    lam = G.demand_rate(h, g, c, d, fests, inc)[0]
                    dem = G.sample_nb(rng_d, lam)
                    m["demand"] += dem
                    served = min(dem, len(stock[k]))
                    stock[k] = stock[k][served:]
                    if dem > served:
                        m["unmet"] += dem - served
                        m["stockout_days"] += 1
                        stockout_log.append((k, day))
                    a = 0.15
                    err = dem - est.get(k, lam)
                    est[k] = (1 - a) * est.get(k, lam) + a * dem
                    var[k] = (1 - a) * var.get(k, lam) + a * err * err
        for k, s in stock.items():
            aged = [x - 1 for x in s]
            m["wasted"] += sum(1 for x in aged if x <= 0)
            stock[k] = [x for x in aged if x > 0]

    for k, day in stockout_log:
        if any(day - 2 <= a <= day for a in alert_log.get(k, [])):
            m["stockouts_warned"] += 1
    so = {(k, dd) for k, dd in stockout_log}
    for k, ds in alert_log.items():
        for a in ds:
            if any((k, a + j) in so for j in range(0, 3)):
                m["alerts_true"] += 1
    m["fulfilment_pct"] = round(100 * (1 - m["unmet"] / max(1, m["demand"])), 2)
    m["alert_recall_48h"] = round(m["stockouts_warned"] / max(1, len(stockout_log)), 3)
    m["alert_precision"] = round(m["alerts_true"] / max(1, m["alerts"]), 3)
    return m


def main(days: int = 90, persist: bool = True) -> dict:
    a, b = run("A", days), run("B", days)
    pct = lambda x, y: round(100 * (x - y) / x, 1) if x else None  # noqa: E731
    out = {
        "days": days, "policy_a": a, "policy_b": b,
        "improvement": {"wastage_reduction_pct": pct(a["wasted"], b["wasted"]),
                        "unmet_reduction_pct": pct(a["unmet"], b["unmet"]),
                        "stockout_days_reduction_pct": pct(a["stockout_days"], b["stockout_days"])},
        "method": "common random numbers; daily resolution; RBC + platelets; see docs/EVALUATION.md",
    }
    if persist:
        import psycopg2

        from app.config import get_settings

        conn = psycopg2.connect(get_settings().sync_database_url_direct.replace("postgresql+psycopg2://", "postgresql://"))
        cur = conn.cursor()
        cur.execute("INSERT INTO eval_results (kind, payload, created_at) VALUES ('replay', %s, now())", (json.dumps(out),))
        conn.commit()
        conn.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--no-persist", action="store_true")
    args = ap.parse_args()
    print(json.dumps(main(args.days, not args.no_persist), indent=1))

"""Demand forecasting (blueprint B6.1).

Models
- seasonal_naive: same weekday last week (baseline every metric is compared against)
- moving_avg_28: trailing 28-day mean
- croston_sba: Syntetos-Boylan approximation for intermittent series (rare groups, small sites)
- lgbm_quantile: ONE global LightGBM model per quantile (q10/q50/q90) across all facilities.
  Features use information up to the forecast origin only (direct multi-horizon), so the same
  model serves horizons 1..14 and cold-start facilities (facility attributes carry the signal).

Pipeline: rolling-origin backtest -> per-group model selection by pinball loss -> split-conformal
interval correction -> 14-day quantile forecasts with driver explanations.
The forecast target is the *statistical* demand (issued minus known scheduled units); the risk
engine adds scheduled demand (thalassemia cohorts) deterministically on top.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from app.domain.rules import ABO_RH, COMPONENTS, GROUP_MIX
from app.ml.calendar import dengue_index, festival_proximity, monsoon_index

log = logging.getLogger(__name__)

HORIZON = 14
QUANTILES = (0.1, 0.5, 0.9)
MODEL_VERSION = "2026.11-1"
SUBTYPES = ("large", "small", "trauma", "maternity", "bank")


@dataclass
class Panel:
    """Dense daily history: y[s, d] with NaN for missing days (missing != zero, edge case #22)."""
    start: date
    keys: list[tuple[int, str, str]]
    y: np.ndarray
    event: np.ndarray
    sched: np.ndarray  # known scheduled units per (s, d), history and future (D + HORIZON)
    facility_attrs: dict[int, dict]
    festivals: dict = field(default_factory=dict)

    @property
    def n_days(self) -> int:
        return self.y.shape[1]

    def day(self, i: int) -> date:
        return self.start + timedelta(days=i)


@dataclass
class SeriesForecast:
    key: tuple[int, str, str]
    q10: list[float]
    q50: list[float]
    q90: list[float]
    scheduled: list[float]
    model: str
    history_days: int
    agreement: float
    drivers: list[dict]
    mean: list[float] = field(default_factory=list)  # expected demand (Poisson-objective model)


# ----------------------------------------------------------------------------- helpers

def _nanmean(a: np.ndarray, axis: int = 1) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        cnt = np.sum(~np.isnan(a), axis=axis)
        s = np.nansum(a, axis=axis)
        return np.where(cnt > 0, s / np.maximum(cnt, 1), np.nan)


def _window(y: np.ndarray, end: int, n: int) -> np.ndarray:
    return y[:, max(0, end - n + 1): end + 1]


def pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.nanmean(np.maximum(alpha * d, (alpha - 1) * d)))


def wape(y: np.ndarray, f: np.ndarray) -> float:
    m = ~np.isnan(y)
    denom = np.sum(np.abs(y[m]))
    return float(np.sum(np.abs(y[m] - f[m])) / denom) if denom > 0 else float("nan")


def poisson_quantile(mu: np.ndarray, q: float, dispersion: float = 1.0) -> np.ndarray:
    """Quantile of an over-dispersed count distribution (normal approx for large mu, exact Poisson small)."""
    mu = np.maximum(np.asarray(mu, dtype=float), 0)
    out = np.zeros_like(mu)
    small = mu < 15
    for i in np.flatnonzero(small):
        m = mu.flat[i] * dispersion
        if m <= 0:
            continue
        k, p, cdf = 0, math.exp(-m), math.exp(-m)
        while cdf < q and k < 200:
            k += 1
            p *= m / k
            cdf += p
        out.flat[i] = k / dispersion if dispersion != 1 else k
    z = {0.1: -1.2816, 0.5: 0.0, 0.9: 1.2816}[q]
    big = ~small
    out[big] = np.maximum(0, mu[big] + z * np.sqrt(mu[big] * dispersion))
    return out


# ----------------------------------------------------------------------------- simple models

def seasonal_naive(p: Panel, origin: int) -> np.ndarray:
    """(S, HORIZON) point forecasts: same weekday in the last observed week, NaN-safe."""
    out = np.zeros((len(p.keys), HORIZON))
    for h in range(1, HORIZON + 1):
        lag = origin + h - 7 * math.ceil(h / 7)
        vals = p.y[:, lag] if 0 <= lag < p.n_days else np.full(len(p.keys), np.nan)
        # fall back to 4-week same-weekday mean, then 28-day mean, when the lag day is missing
        alt = _nanmean(np.stack([p.y[:, lag - 7 * k] if lag - 7 * k >= 0 else np.full(len(p.keys), np.nan)
                                 for k in range(0, 4)], axis=1))
        alt = np.where(np.isnan(alt), _nanmean(_window(p.y, origin, 28)), alt)
        out[:, h - 1] = np.where(np.isnan(vals), alt, vals)
    return np.nan_to_num(out)


def moving_avg(p: Panel, origin: int, n: int = 28) -> np.ndarray:
    m = np.nan_to_num(_nanmean(_window(p.y, origin, n)))
    return np.repeat(m[:, None], HORIZON, axis=1)


def croston_sba(p: Panel, origin: int, alpha: float = 0.1) -> np.ndarray:
    hist = p.y[:, : origin + 1]
    out = np.zeros(len(p.keys))
    for s in range(len(p.keys)):
        z = q = None
        gap = 1
        for v in hist[s, -365:]:
            if np.isnan(v):
                continue
            if v > 0:
                if z is None:
                    z, q = v, gap
                else:
                    z = z + alpha * (v - z)
                    q = q + alpha * (gap - q)
                gap = 1
            else:
                gap += 1
        out[s] = 0.0 if z is None else (1 - alpha / 2) * z / q
    return np.repeat(out[:, None], HORIZON, axis=1)


# ----------------------------------------------------------------------------- global LightGBM

FEATURES = [
    "h", "dow", "month", "doy_sin", "doy_cos", "fest", "dengue", "monsoon", "ma7", "ma28", "ma91",
    "sdw8", "std28", "zero28", "trend", "comp", "group", "group_share", "ftype", "beds", "trauma",
    "subtype", "sched", "hist_days",
]


def _origin_stats(p: Panel, origin: int) -> dict[str, np.ndarray]:
    y = p.y
    ma7 = _nanmean(_window(y, origin, 7))
    ma28 = _nanmean(_window(y, origin, 28))
    ma91 = _nanmean(_window(y, origin, 91))
    w28 = _window(y, origin, 28)
    with np.errstate(invalid="ignore"):
        std28 = np.nanstd(w28, axis=1) if w28.shape[1] else np.full(len(p.keys), np.nan)
        zero28 = _nanmean((w28 == 0).astype(float) + np.where(np.isnan(w28), np.nan, 0))
    hist_days = np.sum(~np.isnan(y[:, : origin + 1]), axis=1).astype(float)
    return {"ma7": ma7, "ma28": ma28, "ma91": ma91, "std28": std28, "zero28": zero28,
            "trend": ma7 / (ma28 + 0.1), "hist_days": hist_days}


def _static_cols(p: Panel) -> dict[str, np.ndarray]:
    comp = np.array([COMPONENTS.index(k[2]) for k in p.keys], dtype=float)
    grp = np.array([ABO_RH.index(k[1]) for k in p.keys], dtype=float)
    share = np.array([GROUP_MIX[k[1]] for k in p.keys])
    fa = [p.facility_attrs.get(k[0], {}) for k in p.keys]
    return {
        "comp": comp, "group": grp, "group_share": share,
        "ftype": np.array([1.0 if a.get("type") == "blood_bank" else 0.0 for a in fa]),
        "beds": np.array([float(a.get("beds", 0)) for a in fa]),
        "trauma": np.array([1.0 if a.get("is_trauma_centre") else 0.0 for a in fa]),
        "subtype": np.array([float(SUBTYPES.index(a.get("subtype", "small"))) if a.get("subtype") in SUBTYPES else 1.0
                             for a in fa]),
    }


def build_features(p: Panel, origin: int, static: dict | None = None) -> np.ndarray:
    """(S * HORIZON, F) feature matrix for one origin. Row order: horizon-major."""
    static = static or _static_cols(p)
    st = _origin_stats(p, origin)
    S = len(p.keys)
    blocks = []
    for h in range(1, HORIZON + 1):
        d = p.day(origin + h)
        doy = d.timetuple().tm_yday
        fest, _ = festival_proximity(d, p.festivals)
        lagdays = [origin + h - 7 * k for k in range(1, 9) if origin + h - 7 * k <= origin]
        sdw = _nanmean(p.y[:, [i for i in lagdays if i >= 0]]) if lagdays and lagdays[-1] >= 0 else np.full(S, np.nan)
        sched_col = p.sched[:, origin + h] if origin + h < p.sched.shape[1] else np.zeros(S)
        cols = {
            "h": np.full(S, h), "dow": np.full(S, d.weekday()), "month": np.full(S, d.month),
            "doy_sin": np.full(S, math.sin(2 * math.pi * doy / 365.25)),
            "doy_cos": np.full(S, math.cos(2 * math.pi * doy / 365.25)),
            "fest": np.full(S, fest), "dengue": np.full(S, dengue_index(d)), "monsoon": np.full(S, monsoon_index(d)),
            "sdw8": sdw, "sched": sched_col, **st, **static,
        }
        blocks.append(np.column_stack([cols[f] for f in FEATURES]).astype(np.float32))
    return np.vstack(blocks)


def _targets(p: Panel, origin: int, clean: np.ndarray) -> np.ndarray:
    idx = [origin + h for h in range(1, HORIZON + 1)]
    out = np.full((HORIZON, len(p.keys)), np.nan)
    for j, i in enumerate(idx):
        if i < p.n_days:
            out[j] = clean[:, i]
    return out.reshape(-1)


def _winsorised(p: Panel) -> np.ndarray:
    """Training hygiene: event days (mass casualty, outbreaks) are replaced by the series' 28-day
    median so a one-off incident does not teach the model a false baseline."""
    y = p.y.copy()
    if p.event.any():
        for s, d in zip(*np.nonzero(p.event), strict=True):
            w = p.y[s, max(0, d - 28): d]
            w = w[~np.isnan(w)]
            y[s, d] = float(np.median(w)) if len(w) else np.nan
    return y


class GlobalQuantileModel:
    def __init__(self, rounds: int = 160):
        self.rounds = rounds
        self.models: dict[float, object] = {}

    def fit(self, p: Panel, last_target_day: int, origin_step: int = 10) -> GlobalQuantileModel:
        import lightgbm as lgb

        clean = _winsorised(p)
        static = _static_cols(p)
        X, Y = [], []
        first = 60
        for origin in range(first, last_target_day - HORIZON + 1, origin_step):
            X.append(build_features(p, origin, static))
            Y.append(_targets(p, origin, clean))
        X, Y = np.vstack(X), np.concatenate(Y)
        keep = ~np.isnan(Y)
        X, Y = X[keep], Y[keep]
        for q in QUANTILES:
            params = {"objective": "quantile", "alpha": q, "learning_rate": 0.06, "num_leaves": 31,
                      "min_data_in_leaf": 40, "feature_fraction": 0.9, "bagging_fraction": 0.8,
                      "bagging_freq": 1, "verbose": -1, "seed": 7, "num_threads": 0}
            self.models[q] = lgb.train(params, lgb.Dataset(X, Y, feature_name=FEATURES), self.rounds)
        # Mean model: the median of an intermittent count series can sit far below its mean, and the
        # risk engine needs the mean. Poisson objective = calibrated expected counts.
        mparams = {"objective": "poisson", "learning_rate": 0.06, "num_leaves": 31, "min_data_in_leaf": 40,
                   "feature_fraction": 0.9, "bagging_fraction": 0.8, "bagging_freq": 1, "verbose": -1, "seed": 7}
        self.models["mean"] = lgb.train(mparams, lgb.Dataset(X, Y, feature_name=FEATURES), self.rounds)
        log.info("lgbm trained on %d rows", len(Y))
        return self

    def predict(self, p: Panel, origin: int) -> dict[float, np.ndarray]:
        X = build_features(p, origin)
        S = len(p.keys)
        out = {}
        for q, m in self.models.items():
            out[q] = np.maximum(0, m.predict(X).reshape(HORIZON, S).T)
        lo, mid, hi = out[0.1], out[0.5], out[0.9]
        mid = np.maximum(mid, lo)
        hi = np.maximum(hi, mid)
        return {0.1: lo, 0.5: mid, 0.9: hi, "mean": np.clip(out["mean"], lo, np.maximum(hi, lo))}


# ----------------------------------------------------------------------------- selection + calibration

def series_group(mean: float, zero_frac: float, comp: str) -> str:
    density = "sparse" if (zero_frac > 0.5 or mean < 0.5) else ("dense" if mean >= 3 else "medium")
    return f"{comp}:{density}"


def _intervals_from_point(point: np.ndarray) -> dict[float, np.ndarray]:
    return {0.1: poisson_quantile(point, 0.1, 1.0), 0.5: point, 0.9: poisson_quantile(point, 0.9, 1.0), "mean": point}


def nb_params(q10: np.ndarray, q50: np.ndarray, q90: np.ndarray, mean=None) -> tuple[np.ndarray, np.ndarray]:
    """The SAME predictive distribution the risk engine samples from (risk_sim.nb_params)."""
    from app.ml.risk_sim import nb_params as _nb

    return _nb(q10, q50, q90, mean)


def nb_cdf(y: np.ndarray, r: np.ndarray, p: np.ndarray) -> np.ndarray:
    """P(Y <= y) for integer y >= -1, vectorised via the pmf recursion."""
    y = np.asarray(y, dtype=np.int64)
    pmf = np.exp(r * np.log(p))
    cdf = np.where(y >= 0, pmf, 0.0)
    for k in range(0, int(max(0, y.max()))):
        pmf = pmf * (k + r) / (k + 1) * (1 - p)
        cdf = cdf + np.where(y >= k + 1, pmf, 0.0)
    return np.clip(cdf, 0, 1)


def pit_coverage(y: np.ndarray, q10: np.ndarray, q50: np.ndarray, q90: np.ndarray, seed: int = 11, mean=None) -> float:
    """Randomised PIT coverage of the central 80% band. For integer counts an inclusive interval
    always over-covers (ties at 0); the randomised PIT is the standard calibration check there."""
    if len(y) == 0:
        return float("nan")
    r, p = nb_params(q10, q50, q90, mean)
    lo, hi = nb_cdf(y - 1, r, p), nb_cdf(y, r, p)
    u = lo + np.random.default_rng(seed).random(len(y)) * (hi - lo)
    return float(np.mean((u >= 0.1) & (u <= 0.9)))


def adjusted(q10: np.ndarray, q50: np.ndarray, q90: np.ndarray, s: float) -> tuple[np.ndarray, np.ndarray]:
    """Scale the interval half-widths around the median by s (s=1: unchanged)."""
    return np.maximum(0, q50 - s * (q50 - q10)), q50 + s * (q90 - q50)


SCALE_GRID = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.5, 3.0)


def calibrate_interval(y: np.ndarray, q10: np.ndarray, q50: np.ndarray, q90: np.ndarray, target: float = 0.8,
                       mean=None) -> float:
    """Split-conformal style width calibration: pick the scale whose randomised-PIT coverage on the
    calibration split is closest to target (grid search; coverage is not monotone across mixed series)."""
    yi = np.nan_to_num(y).astype(np.int64)
    best = min(SCALE_GRID, key=lambda s: (abs(pit_coverage(yi, *_triple(q10, q50, q90, s), mean=mean) - target), abs(s - 1)))
    return float(best)


def _triple(q10, q50, q90, s):
    lo, hi = adjusted(q10, q50, q90, s)
    return lo, q50, hi


def _all_models(p: Panel, origin: int, lgbm: GlobalQuantileModel | None) -> dict[str, dict[float, np.ndarray]]:
    out = {
        "seasonal_naive": _intervals_from_point(seasonal_naive(p, origin)),
        "moving_avg_28": _intervals_from_point(moving_avg(p, origin)),
        "croston_sba": _intervals_from_point(croston_sba(p, origin)),
    }
    if lgbm is not None:
        try:
            out["lgbm_quantile"] = lgbm.predict(p, origin)
        except Exception as exc:  # noqa: BLE001 - circuit breaker: model failure never breaks the cycle
            log.warning("lgbm predict failed: %s", exc)
    return out


@dataclass
class BacktestReport:
    metrics: dict  # group -> model -> {wape, pinball, coverage80, n}
    chosen: dict[str, str]  # group -> model
    conformal: dict[str, float]  # group -> interval width scale
    overall: dict


def backtest(p: Panel, n_origins: int = 4, step: int = 14) -> tuple[BacktestReport, dict[int, str]]:
    """Rolling-origin backtest. LightGBM is trained once on data before the first origin."""
    last = p.n_days - 1
    origins = [last - HORIZON - step * i for i in range(n_origins)][::-1]
    lgbm = None
    try:
        lgbm = GlobalQuantileModel(rounds=120).fit(p, origins[0])
    except Exception as exc:  # noqa: BLE001
        log.warning("backtest lgbm training failed: %s", exc)

    st = _origin_stats(p, origins[0])
    groups = [series_group(float(np.nan_to_num(st["ma28"][s])), float(np.nan_to_num(st["zero28"][s], nan=1.0)), k[2])
              for s, k in enumerate(p.keys)]
    acc: dict[str, dict[str, dict[str, list]]] = {}
    scores: dict[str, dict[str, list]] = {}
    for oi, origin in enumerate(origins):
        truth = np.stack([p.y[:, origin + h] if origin + h < p.n_days else np.full(len(p.keys), np.nan)
                          for h in range(1, HORIZON + 1)], axis=1)
        for name, q in _all_models(p, origin, lgbm).items():
            for s, g in enumerate(groups):
                a = acc.setdefault(g, {}).setdefault(name, {"y": [], "q10": [], "q50": [], "q90": [], "o": [], "mu": []})
                a["mu"].append(q["mean"][s])
                a["y"].append(truth[s]); a["q10"].append(q[0.1][s]); a["q50"].append(q[0.5][s]); a["q90"].append(q[0.9][s])
                a["o"].append(np.full(HORIZON, oi))

    metrics: dict = {}
    chosen: dict[str, str] = {}
    conformal: dict[str, float] = {}
    tot = {"y": [], "naive": [], "best": [], "q10": [], "q90": [], "q10r": [], "q90r": [], "hold": [], "mu": []}
    half = n_origins // 2
    for g, models in acc.items():
        metrics[g] = {}
        for name, a in models.items():
            y, q10, q50, q90, o, mu = (np.concatenate(a[k]) for k in ("y", "q10", "q50", "q90", "o", "mu"))
            m = ~np.isnan(y)
            pl = np.mean([pinball(y, q10, 0.1), pinball(y, q50, 0.5), pinball(y, q90, 0.9)])
            cov = float(np.mean((y[m] >= q10[m]) & (y[m] <= q90[m]))) if m.any() else float("nan")
            metrics[g][name] = {"wape": round(wape(y, q50), 4), "pinball": round(float(pl), 4),
                                "coverage80_raw": round(cov, 3), "n": int(m.sum())}
            scores.setdefault(g, {})[name] = [y, q10, q50, q90, o, mu]
        best = min(metrics[g], key=lambda n: (metrics[g][n]["pinball"], n != "lgbm_quantile"))
        chosen[g] = best
        y, q10, q50, q90, o, mu = scores[g][best]
        m = ~np.isnan(y)
        cal = m & (o < half)  # calibrate on early origins, evaluate coverage on later (held-out) ones
        conformal[g] = calibrate_interval(y[cal], q10[cal], q50[cal], q90[cal], mean=mu[cal]) if cal.sum() > 20 else 1.0
        lo_c, hi_c = adjusted(q10, q50, q90, conformal[g])
        tot["y"].append(y); tot["naive"].append(scores[g]["seasonal_naive"][2]); tot["best"].append(q50)
        tot["q10"].append(lo_c); tot["q90"].append(hi_c)
        tot["q10r"].append(q10); tot["q90r"].append(q90); tot["hold"].append(o >= half); tot["mu"].append(mu)

    y, nv, bs = (np.concatenate(tot[k]) for k in ("y", "naive", "best"))
    q10c, q90c, q10r, q90r = (np.concatenate(tot[k]) for k in ("q10", "q90", "q10r", "q90r"))
    m = ~np.isnan(y) & np.concatenate(tot["hold"])
    mu_all = np.concatenate(tot["mu"])
    yi = np.nan_to_num(y[m]).astype(np.int64)
    overall = {
        "wape_baseline": round(wape(y, nv), 4), "wape_raktsetu": round(wape(y, bs), 4),
        "pinball50_baseline": round(pinball(y, nv, 0.5), 4), "pinball50_raktsetu": round(pinball(y, bs, 0.5), 4),
        "coverage80_raw_holdout": round(pit_coverage(yi, q10r[m], bs[m], q90r[m], mean=mu_all[m]), 3),
        "coverage80_calibrated": round(pit_coverage(yi, q10c[m], bs[m], q90c[m], mean=mu_all[m]), 3),
        "mean_bias_ratio": round(float(np.sum(mu_all[m]) / max(np.sum(y[m]), 1e-9)), 3),
        "coverage80_inclusive_calibrated": round(float(np.mean((y[m] >= q10c[m]) & (y[m] <= q90c[m]))), 3),
        "coverage_note": "randomised-PIT coverage of the negative-binomial predictive distribution on held-out "
                         "origins; width adjustment fitted on earlier origins only. Inclusive interval coverage "
                         "over-states on integer counts and is shown for transparency.",
        "origins": [p.day(o).isoformat() for o in origins], "horizon_days": HORIZON, "series": len(p.keys),
    }
    overall["wape_improvement_pct"] = round(100 * (1 - overall["wape_raktsetu"] / overall["wape_baseline"]), 1) \
        if overall["wape_baseline"] else None
    series_choice = {s: chosen[g] for s, g in enumerate(groups)}
    return BacktestReport(metrics, chosen, conformal, overall), series_choice


def drivers_for(p: Panel, s: int, origin: int, model: str, event_mode: bool = False) -> list[dict]:
    """Human-readable forecast drivers shown as chips in the UI and fed to Gemini explanations."""
    out: list[dict] = []
    comp = p.keys[s][2]
    for h in range(1, 8):
        d = p.day(origin + h)
        w, name = festival_proximity(d, p.festivals)
        if name and w >= 0.5:
            out.append({"kind": "festival", "label": f"{name} ({d.isoformat()})", "weight": round(w, 2)})
            break
    di = dengue_index(p.day(origin + 1))
    if comp == "PLT" and di > 0.3:
        out.append({"kind": "dengue", "label": "Dengue season platelet demand", "weight": round(di, 2)})
    mi = monsoon_index(p.day(origin + 1))
    if mi > 0.4:
        out.append({"kind": "monsoon", "label": "Monsoon period", "weight": round(mi, 2)})
    st7 = _nanmean(_window(p.y[s: s + 1], origin, 7))[0]
    st28 = _nanmean(_window(p.y[s: s + 1], origin, 28))[0]
    if not np.isnan(st7) and not np.isnan(st28) and st28 > 0.3:
        r = st7 / st28
        if r > 1.25:
            out.append({"kind": "trend", "label": f"Demand up {100 * (r - 1):.0f}% vs 4-week average", "weight": round(r, 2)})
        elif r < 0.75:
            out.append({"kind": "trend", "label": f"Demand down {100 * (1 - r):.0f}% vs 4-week average", "weight": round(r, 2)})
    sched = p.sched[s, origin + 1: origin + 8].sum() if p.sched.shape[1] > origin + 1 else 0
    if sched > 0:
        out.append({"kind": "scheduled", "label": f"{int(sched)} scheduled thalassemia units in 7 days", "weight": float(sched)})
    out.append({"kind": "weekday", "label": "Weekday surgery pattern", "weight": 1.0})
    if event_mode:
        out.append({"kind": "event", "label": "Event mode: demand spike detected", "weight": 1.0})
    out.append({"kind": "model", "label": f"Model: {model}", "weight": 1.0})
    return out


def forecast_all(p: Panel) -> tuple[list[SeriesForecast], BacktestReport]:
    """Full daily pipeline: backtest, select, train final, calibrate, forecast 14 days."""
    report, choice = backtest(p)
    origin = p.n_days - 1
    lgbm = None
    try:
        lgbm = GlobalQuantileModel().fit(p, origin)
    except Exception as exc:  # noqa: BLE001
        log.warning("final lgbm training failed, falling back: %s", exc)
    models = _all_models(p, origin, lgbm)
    st = _origin_stats(p, origin)
    groups = [series_group(float(np.nan_to_num(st["ma28"][s])), float(np.nan_to_num(st["zero28"][s], nan=1.0)), k[2])
              for s, k in enumerate(p.keys)]

    # Cold-start shrinkage toward the cluster mean (same facility subtype, group, component).
    cluster: dict[tuple, list[float]] = {}
    for s, k in enumerate(p.keys):
        if st["hist_days"][s] >= 28 and not np.isnan(st["ma28"][s]):
            sub = p.facility_attrs.get(k[0], {}).get("subtype")
            cluster.setdefault((sub, k[1], k[2]), []).append(float(st["ma28"][s]))

    out = []
    for s, key in enumerate(p.keys):
        g = groups[s]
        name = choice.get(s, report.chosen.get(g, "seasonal_naive"))
        if name not in models:
            name = "seasonal_naive"
        q = models[name]
        lo, mid, hi, mu = q[0.1][s].copy(), q[0.5][s].copy(), q[0.9][s].copy(), q["mean"][s].copy()
        adj = report.conformal.get(g, 1.0)
        lo, hi = adjusted(lo, mid, hi, adj)
        hist = int(st["hist_days"][s])
        if hist < 28:
            sub = p.facility_attrs.get(key[0], {}).get("subtype")
            prior = float(np.mean(cluster.get((sub, key[1], key[2]), [float(mid.mean())])))
            w = hist / (hist + 28)
            mid = w * mid + (1 - w) * prior
            mu = w * mu + (1 - w) * prior
            lo = np.minimum(lo, mid * 0.3)
            hi = np.maximum(hi, mid * 2.5 + 1)  # wide interval -> low confidence badge
            name = f"{name}+coldstart"
        naive = models["seasonal_naive"][0.5][s]
        agree = float(1 - min(1.0, abs(mid.mean() - naive.mean()) / (mid.mean() + naive.mean() + 1)))
        sched = [float(p.sched[s, origin + h]) if origin + h < p.sched.shape[1] else 0.0 for h in range(1, HORIZON + 1)]
        out.append(SeriesForecast(key, [round(float(v), 3) for v in lo], [round(float(v), 3) for v in mid],
                                  [round(float(v), 3) for v in hi], sched, name, hist, round(agree, 3),
                                  drivers_for(p, s, origin, name), [round(float(v), 3) for v in np.clip(mu, lo, np.maximum(hi, lo))]))
    return out, report

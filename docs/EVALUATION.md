# Evaluation

All numbers below are produced by code (`make seed` -> backtest; `make replay` -> policy comparison) on the
synthetic ground truth in docs/DATA_CARD.md, and are shown live on the Evaluation page. Re-running
reproduces them (fixed seeds). They are targets met on synthetic data, not clinical claims.

## 1. Forecast backtest (rolling origin)
4 origins, 14 days apart, horizon 1-14 days, 992 series. LightGBM trained once on data before the first
origin; interval calibration fitted on origins 1-2, coverage measured on origins 3-4 (held out).

| Metric | Seasonal-naive baseline | RaktSetu | Target |
|---|---|---|---|
| WAPE (point, 14-day) | 1.051 | **0.738 (-29.8%)** | >= 15% lower ✅ |
| Median pinball loss | 0.324 | **0.227** | lower ✅ |
| 80% interval coverage (randomised PIT, held-out) | - | raw 0.792 -> **0.803** calibrated | 0.75-0.85 ✅ |
| Mean-model bias (held-out) | - | **+20%** over-forecast | report honestly ⚠️ |

Model selection per group (pinball): LightGBM wins 9 of 10 groups; Croston SBA wins dense FFP.
Why PIT: for zero-heavy integer counts an inclusive interval always over-covers (inclusive coverage is
0.96); the randomised PIT of the negative-binomial predictive distribution - the exact distribution the
risk engine samples - is the standard calibration check for discrete forecasts.
The +20% bias falls in the post-dengue decline (Oct-Nov) where the model still carries the platelet peak;
it errs on the safe side (more warnings) and is a known limitation.

## 2. Closed-loop replay (90 days)
`scripts/replay_sim.py`. Identical demand, donations and starting stock for both policies (common random numbers).
- **Policy A (static):** order from district bank when below a fixed threshold, up to 2x threshold; no lateral moves.
- **Policy B (RaktSetu):** forecast-driven order-up-to levels with variance-based safety stock (shorter for
  platelets), NB-tail 48 h stockout warnings, lateral transfers from peers above their own safety stock,
  use-it-or-move-it of near-expiry units.

| Metric | Policy A | Policy B | Change |
|---|---|---|---|
| Wasted (expired) units | 3,773 | 2,229 | **-40.9%** |
| Unmet units | 5,082 | 2,937 | **-42.2%** |
| Stockout series-days | 2,748 | 2,097 | -23.7% |
| Fulfilment | 88.9% | 93.6% | +4.7 pts |
| Alerts raised | 15,785 | 2,080 | 7.6x fewer |
| 48 h alert recall | 0.71 | 0.17 | lower ⚠️ |
| Alert precision | 0.22 | 0.27 | higher |

Honest reading: RaktSetu prevents far more shortages and wastage, with far fewer alerts. Its *recall* is
lower because most remaining stockouts are bursts in rare series (e.g. AB- platelets at ~0.02 units/day)
that no calibrated model can flag without alert fatigue; the static policy "recalls" them by alerting on
almost every low-stock day. Threshold is a tunable trade-off.

Simplifications: daily resolution, RBC + platelets, district banks as supply hubs, transfers arrive next
day. The live system works hourly with the full Monte Carlo engine and OR-Tools; the replay is evidence of
direction and rough magnitude.

## 3. System performance (local, warm)
- Forecast pipeline (backtest + train + calibrate + 14-day forecasts): ~30 s per day.
- Risk engine: ~850 active series x 2,000 paths x 168 h in ~3 s (exact vectorised FEFO).
- Full hourly cycle: ~35 s (forecast) / ~6 s (risk + plan only). API dashboard endpoints: 4-20 ms.
- Optimizer: 300-facility synthetic network solved within the 20 s test budget.

# RaktSetu - AI-Powered Predictive Blood Network

**Predict blood shortages before they become emergencies, and coordinate hospitals and blood banks to prevent them.**

One hospital runs out of O-negative while another discards expired units the same week. RaktSetu
("blood bridge") is a shared early-warning radar for blood that turns each warning into an approved,
constraint-checked action.

> Synthetic data only (see [Data Card](docs/DATA_CARD.md)). Decision support, not a medical device:
> humans approve every transfer; substitutions need clinician sign-off.

## Chosen vertical

**Healthcare operations — blood-bank and hospital supply coordination.** RaktSetu addresses a
network problem: a shortage at one facility can occur alongside avoidable expiry at another because
stock, demand signals and transfer decisions are fragmented. The product is designed for hospital
transfusion teams, blood-bank managers and regional coordinators—not patients—and supports their
decisions without replacing clinical judgement.

## Approach and logic

RaktSetu uses a closed-loop operational approach rather than a simple low-stock alert:

1. **Record truth at unit level.** Every donation, issue, reservation, expiry and transfer is written
   to an append-only inventory ledger. The current stock status is derived from that ledger, with
   FEFO (first-expiry, first-out) used throughout.
2. **Forecast uncertain demand.** Historical consumption, weekday patterns, scheduled demand,
   festivals and seasonal signals produce 14-day q10/q50/q90 forecasts plus a mean estimate for
   each facility, blood group and component.
3. **Simulate stockout risk.** The risk engine runs 2,000 FEFO-aware demand paths per series. It
   accounts for remaining shelf life, forecast uncertainty, known incoming stock and transfer lead
   time to calculate time-to-stockout and 24/48/72-hour stockout probability.
4. **Optimize a feasible response.** When risk or expiry warrants action, an OR-Tools MIP proposes
   transfers under ABO/Rh compatibility, minimum life-on-arrival, cold-chain travel time, donor
   safety stock and stability constraints. Non-identical blood-group substitutions are explicitly
   marked for clinician approval.
5. **Keep humans in control.** A coordinator approves or rejects a proposal; the sending facility
   dispatches and the receiving facility confirms receipt. Every write is idempotent and audited.

## How the solution works

```text
Facility stock + consumption history
        ↓
Append-only unit ledger → forecast demand → simulate FEFO stockout risk
        ↓                                      ↓
Coordinator dashboard ← optimized, explainable transfer proposals
        ↓
Human approval → dispatch → receipt → updated ledger and live risk view
```

- **Operations workspace:** role-scoped React dashboards show risk, expiry exposure, facility stock,
  transfer approvals, evaluation results and a mass-casualty what-if tool.
- **Identity and onboarding:** Firebase Authentication creates an account; the user requests a
  hospital or blood-bank role; a regional coordinator approves it; Firebase custom claims then scope
  the user to the appropriate facility or region.
- **Responsible AI assistance:** Gemini can explain an approved-data plan, draft consent-based donor
  appeals and extract a paper register. It may only call read-only tools; numerical statements are
  checked against tool output and every feature has a non-AI template fallback.
- **Graceful deployment:** the same API works with Firebase/Cloud Run or the no-card Render path,
  backed by Neon Postgres. Optional Firestore, FCM, Maps, Calendar, BigQuery and AI integrations
  degrade without blocking the core ledger, forecasting or transfer workflow.

## Assumptions

- All facilities, inventory, donor records and outcomes in this repository are synthetic; no patient
  data or real donor contact details are used.
- Facility stock updates are sufficiently timely for the next hourly planning cycle; stale reporting
  is surfaced to operators rather than silently treated as zero stock.
- Shelf-life rules and compatibility rules are clinically governed configuration in the database.
  The application does not auto-substitute blood groups.
- Travel estimates are approximate when the Google Routes API is unavailable; the system falls back
  to a documented haversine-based estimate and retains human approval.
- The tool is decision support, not a medical device. Clinical staff remain responsible for patient
  suitability, compatibility decisions and final transfer approval.

## What it does
| | Feature | How |
|---|---|---|
| Predict | **Probabilistic time-to-stockout** per facility x group x component, P(stockout) at 24/48/72 h, with confidence | Global LightGBM quantile + Poisson-mean models, Croston for rare groups, PIT-calibrated; exact vectorised FEFO Monte Carlo (2,000 paths), lead-time aware |
| Protect | **Use it or move it**: unit-level expiry, FEFO, rescue of near-expiry units | Expected-wastage simulation feeds the optimizer's rescue bonus |
| Coordinate | **Transfer optimizer** + approval workflow (propose -> approve -> dispatch -> receive) | Google OR-Tools MIP: ABO/Rh, shelf life on arrival, cold-chain ETA, donor safety stock, stability |
| Stress test | Click the map, inject a mass-casualty incident, watch facilities break and the response plan | Re-runs risk + optimizer as a what-if |
| Explain | **Gemini copilot** (Hindi/English), "why this plan?", donor appeals, photo-of-register OCR | Read-only tools, numeric post-check of every number, template fallbacks |
| Prove | Backtests and a 90-day closed-loop replay vs a static-threshold policy | [Evaluation](docs/EVALUATION.md) |

## Results on synthetic ground truth (reproducible: `make seed && make replay`)
- Forecast WAPE **-29.8%** vs seasonal-naive (0.738 vs 1.051), 80% interval coverage **80.3%** on held-out origins.
- 90-day replay vs static thresholds: wastage **-40.9%**, unmet demand **-42.2%**, fulfilment 88.9% -> 93.6%, **7.6x fewer alerts**.
- Honest limits: mean model over-forecasts by 20% on the held-out window; 48 h alert recall is lower than
  the always-alerting baseline (rare-group bursts). Both are documented, not hidden.

## Google stack
Gemini (AI Studio or Vertex AI) · Firebase Auth (role claims) · Firestore (live feed) · Firebase Cloud
Messaging · Firebase Hosting · Remote Config + Analytics · Google Maps JS (Advanced Markers + deck.gl heat
layer) · Routes API · Google Calendar API (festivals) · Google OR-Tools · Cloud Run · Cloud Scheduler
(OIDC) · Secret Manager · Cloud Build + Artifact Registry · BigQuery sandbox + Looker Studio · Cloud
Logging. Every integration degrades gracefully when its credentials are absent.

## Architecture
React SPA (Firebase Hosting) -> `/api/**` -> FastAPI on Cloud Run -> Neon Postgres (ledger = truth).
Cloud Scheduler runs the hourly cycle (forecast -> risk -> optimizer -> alerts); Firestore mirrors alerts
and change pings for live browsers. Full details, invariants and decision log:
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Run locally (5 minutes, no cloud accounts needed)
```bash
make db install migrate seed replay   # Postgres in Docker, deps, schema, synthetic data, evaluation
make api                              # http://localhost:8000/docs
make web                              # http://localhost:5173 -> pick a demo role
make test lint                        # 137 backend tests + 25 frontend tests; ruff, ESLint, tsc
```
Demo roles: **Regional coordinator** (whole network), **Blood bank manager** (Delhi Central Blood Bank),
**Hospital transfusion officer** (one hospital only - try to see another facility's data).

## Deploy
Option B (Cloud Run + Firebase Hosting) or Option A (Render + Firebase Hosting, no card): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Robustness and responsible AI
- 46-item [edge-case playbook](docs/EDGE_CASES.md), each linked to a test or marked as a known limitation.
- Idempotent append-only ledger; 50 concurrent reservations for 10 units -> exactly 10 succeed.
- Role-scoped data on every endpoint and in Firestore rules; donor phones hashed, first names only (DPDP Act principles).
- Gemini never computes numbers; untrusted text is fenced; a prompt-injection canary is seeded in the data.
- Audit log of every human decision; model name and version stored with every forecast.

## Code quality and testing
- **Backend:** 137 pytest tests (pure logic, Hypothesis properties, Postgres-backed concurrency, RBAC, alerting,
  onboarding, LLM fallback), `ruff` with security rules.
- **Frontend:** strict TypeScript with **zero `any`**; every API response is typed (`frontend/src/api/types.ts`)
  and reached through one typed client (`frontend/src/api/endpoints.ts`). ESLint (typescript-eslint, React hooks
  rules) runs with `--max-warnings 0`. 25 Vitest + Testing Library tests cover data helpers, the API layer
  (URL building, idempotency keys, error mapping), accessible UI components and content integrity.
- **CI** (`.github/workflows/ci.yml`): backend lint + migrations + tests, frontend lint + typecheck + tests + build,
  and a gitleaks secret scan on every push.

## Docs
[Architecture](docs/ARCHITECTURE.md) · [Data Card](docs/DATA_CARD.md) · [Edge cases](docs/EDGE_CASES.md) ·
[Evaluation](docs/EVALUATION.md) · [API contract](docs/API_CONTRACT.md) · [Demo script](docs/DEMO.md) · [Deployment](docs/DEPLOYMENT.md)

Built with Claude Code (backend, ML, optimizer, tests, infra, docs) and designed for Google Antigravity
(UI iteration and browser-agent verification). Limitations: synthetic data, not clinically validated,
regulations vary by licence; a pilot with real facilities is the next step.

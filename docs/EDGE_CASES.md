# Edge-case playbook (46 items)

Status: ✅ handled and tested · 🟡 handled, test is manual/partial · ⛔ known limitation.
Test paths are relative to `backend/tests/`. Run everything with `make test`.

## Data integrity and inventory
| # | Edge case | How RaktSetu handles it | Status / test |
|---|---|---|---|
| 1 | Duplicate submissions (retry, double-click, offline sync) | `Idempotency-Key` + unique `(facility_id, idempotency_key)`; event row inserted first so concurrent duplicates block then replay; stock derived from ledger | ✅ `test_db_ledger.py::test_duplicate_submissions_create_one_event`, `::test_concurrent_duplicate_keys_are_safe` |
| 2 | Two hospitals reserve the last unit simultaneously | `SELECT ... FOR UPDATE SKIP LOCKED` FEFO pick + TTL | ✅ `::test_fifty_parallel_reservations_for_ten_units` (exactly 10 of 50), `::test_reservation_ttl_releases_units` |
| 3 | Facility stops updating | freshness badge, confidence decay, pessimistic stock deduction after 12 h, "data silent" alert | ✅ `test_risk_sim.py::test_confidence_decays_with_staleness`; seeded SH-04 silent 50 h shows badge + alert |
| 4 | Impossible values (negative, expiry < collection, "C+") | Pydantic validators + DB CHECK constraints; 422 with reason; payload kept in `rejected_entries` | ✅ `test_db_ledger.py::test_impossible_values_rejected_and_kept` (5 cases) |
| 5 | Unit confusion (units vs mL) | component enum, per-component volume range | ✅ same test (3500 mL RBC rejected) |
| 6 | Timezone / expiry ambiguity | timezone-aware timestamps required; UTC in DB; IST for business dates and UI; platelets expire at exact time | ✅ same test (naive timestamp rejected) |
| 7 | Late / back-dated entries | `event_time` vs `ingest_time`; consumption bucketed by event date; forecasts versioned by run | ✅ `::test_backdated_event_keeps_event_and_ingest_time` |
| 8 | Facility merges / closes | `active`, `effective_from/to` columns; inactive facilities rejected for events; history kept | 🟡 schema + `record_event` check; no merge endpoint yet (ARCHITECTURE §16) |

## Expiry and clinical rules
| # | Edge case | Handling | Status / test |
|---|---|---|---|
| 9 | Near-expiry units counted as available | usable stock excludes units under component minimum life; separate expiry buckets | ✅ `test_db_ledger.py::test_near_expiry_units_not_usable` (11 h vs 13 h platelets) |
| 10 | Units expire / exceed cold chain in transit | optimizer requires life on arrival and ETA <= max transit; approval re-checks; in-transit excluded both sides; overdue detection | ✅ `test_compat_optimizer.py::test_cold_chain_limit_rejects_long_transfers`, `test_db_workflows.py::test_units_without_enough_life_on_arrival_block_approval`, `::test_full_lifecycle...` |
| 11 | Quarantined / recalled units appear available | status excluded; recall by donation id quarantines all sibling components at all facilities | ✅ `test_db_ledger.py::test_quarantined_and_reserved_excluded_and_recall_blocks_siblings` |
| 12 | Unsafe automatic substitution | never automatic; substitutes flagged, need `clinician_ack`; O- / Rh- stock conserved for Rh- patients | ✅ `test_compat_optimizer.py::test_substitutes_need_clinician_and_conserve_rh_negative`, `test_db_workflows.py::test_substitution_requires_clinician_ack`, 64-case matrix test |
| 13 | Platelets treated like red cells | per-component forecasts and shelf-life rules; 60 h minimum life on arrival | ✅ `::test_platelets_with_short_life_are_not_transferred` |
| 14 | Special-requirement units (irradiated, CMV-safe) | unit attribute flags; availability search filters `irradiated` / `cmv_safe` pools | 🟡 implemented in `services/availability.py`; optimizer does not yet split pools by attribute |
| 15 | Reserved units look available | available = on-hand minus reserved/locked; scheduled demand layered into risk | ✅ `test_db_ledger.py::test_quarantined_and_reserved_excluded...`, `test_db_workflows.py::test_full_lifecycle...` |

## Forecasting
| # | Edge case | Handling | Status / test |
|---|---|---|---|
| 16 | New facility with zero history | global LightGBM with facility attributes + shrinkage to cluster mean + wide interval -> low confidence | ✅ `test_forecast_guards.py::test_cold_start_series_is_finite`; seeded SH-13 shows `+coldstart` model |
| 17 | Rare groups mostly zero | Croston SBA / NB; mean model so risk is not understated; probabilities reported | ✅ `::test_sparse_series_never_negative_or_nan`, `test_risk_sim.py::test_mean_drives_demand_not_median` |
| 18 | Mass casualty / outbreak spike | anomaly z-score -> event mode multiplier; manual incident events; stress-test simulator; event days winsorised in training | ✅ stress test endpoint + UI; 🟡 anomaly detector exercised in live cycle only |
| 19 | Festivals move each year | Google Calendar API holidays + static table per year | ✅ `test_forecast_guards.py::test_festivals_move_between_years` |
| 20 | Concept drift | per-group model selection on the most recent rolling-origin backtest; naive wins if ML degrades | 🟡 selection runs daily; no separate 7-day drift alarm |
| 21 | Overconfident intervals | PIT-based width calibration on early origins, coverage reported on held-out origins (0.803) | ✅ `::test_pit_coverage_is_about_80_percent_for_a_correct_model`; Evaluation page |
| 22 | Missing days mistaken for zero | NaN vs 0 in panel; `close_day` writes zeros only for facilities that reported | ✅ `::test_missing_days_do_not_lower_the_forecast` |
| 23 | Model failure / timeout | try/except circuit around LightGBM -> baselines; rule-based days-of-cover if no forecast; `model_used` returned | ✅ `test_risk_sim.py::test_rule_based_fallback` |

## Optimisation and logistics
| # | Edge case | Handling | Status / test |
|---|---|---|---|
| 24 | No feasible donor (everyone short) | partial plan + deficits list -> regional-deficit alert + donor appeal prompt | ✅ `test_compat_optimizer.py::test_all_short_returns_partial_plan_and_deficits` |
| 25 | Helping depletes the donor | safety stock = max(P90 x horizon, floor); at-risk facilities never donate | ✅ `::test_optimizer_never_breaches_donor_safety_stock` (Hypothesis), `::test_at_risk_facility_never_donates` |
| 26 | Hospitals over-request | manual requests > 2x forecast need flagged for review; audit | ✅ `test_db_workflows.py::test_manual_overrequest_is_flagged` |
| 27 | Traffic / road closures | Routes API traffic-aware ETA with cache; haversine fallback on failure | 🟡 fallback path covered by all optimizer tests (no key); live API path manual |
| 28 | Recommendations flicker | stability bonus for previous pairs, deterministic solver, severity hysteresis | ✅ `::test_plan_is_stable_across_runs`, `test_risk_sim.py::test_hysteresis_holds_then_releases` |
| 29 | Transfers rejected / not collected / partial | state machine, approval timeout (6 h) releases units, cancel returns units | ✅ `test_db_workflows.py::test_cancel_releases_units`, `::test_invalid_transition_rejected` |
| 30 | Hundreds of facilities | K-nearest candidates, per (group, component) decomposition, 5 s solver limit | ✅ `test_compat_optimizer.py::test_three_hundred_facilities_within_time_budget` |

## Gemini and AI safety
| # | Edge case | Handling | Status / test |
|---|---|---|---|
| 31 | Hallucinated numbers | numeric post-check vs tool JSON; retry; template answer; "data as of" | ✅ `test_forecast_guards.py::test_numeric_check_catches_hallucinated_numbers` (+ Hindi digits) |
| 32 | Prompt injection via notes / OCR | `<untrusted_data>` fencing, tool allowlist, read-only tools, OCR prompt ignores page instructions; seeded injection canary in SH-07 note | ✅ `test_db_workflows.py::test_copilot_tools_are_read_only_allowlist`, `test_forecast_guards.py::test_injection_detector` |
| 33 | OCR misreads | per-field confidence, low-confidence fields block commit, duplicate detection, server re-validation, never auto-commit | 🟡 `features.review_rows` logic; manual test with a real photo needs a Gemini key |
| 34 | Gemini outage / quota | circuit breaker + rate limit + templates for every feature | ✅ `test_db_workflows.py::test_copilot_template_fallback_without_gemini` |
| 35 | Donor message tone / privacy | eligibility in code, first name only, STOP opt-out validated, no numbers/medical claims requested, sending simulated | 🟡 template path tested via UI; snapshot test TODO |

## Infrastructure and operations
| # | Edge case | Handling | Status / test |
|---|---|---|---|
| 36 | Neon cold start / connection limits | pooled URL, `pool_pre_ping`, `pool_recycle`, statement cache off behind pooler, Cloud Run min instance 1, `scripts/smoke.py` warm-up | 🟡 manual (smoke prints readyz latency) |
| 37 | LISTEN/NOTIFY fails behind pooler | Firestore fan-out instead | ✅ by design (`services/realtime.py`) |
| 38 | Multiple instances duplicate scheduled work | stateless app + lease lock + idempotent jobs | ✅ `test_db_workflows.py::test_job_lock_prevents_overlapping_cycles` |
| 39 | Secret leakage | Secret Manager, restricted keys, gitleaks in CI, prod refuses default demo secret | ✅ CI `secrets` job; `main.py` guard |
| 40 | Free-tier limits | forecasts keep latest run only; risk snapshots 3-day retention; route cache; BigQuery load jobs (sandbox) | ✅ code paths in `forecasting.py`, `risk.py` |
| 41 | Poor connectivity | idempotent writes make retries safe; register-photo path; PWA manifest | ⛔ offline queue not implemented |

## Security, privacy and ethics
| # | Edge case | Handling | Status / test |
|---|---|---|---|
| 42 | Cross-facility leakage | claims-based scoping on every endpoint; Firestore rules mirror it | ✅ `test_db_workflows.py::test_rbac_scoping`, `test_db_ledger.py::test_cannot_write_to_other_facility` |
| 43 | Donor PII | hashed phones, first names, PIN centroids, consent/opt-out, no PII in logs (DPDP Act 2023 principles) | ✅ by design; 🟡 no automated log-scrub test |
| 44 | Over-trust in AI | human approval for every transfer, explicit clinician checkbox, "why" drawer, disclaimers | ✅ `test_db_workflows.py::test_hospital_user_cannot_approve` |
| 45 | Alert fatigue | medium silent, dedupe, 6 h cooldown, escalation, auto-resolve; replay shows 7.6x fewer alerts | ✅ `::test_alert_dedupe_escalation_and_autoresolve`; replay metrics |
| 46 | Accessibility and language | Hindi/English, Okabe-Ito palette + text + shape, skip link, keyboard drawer, mobile nav | 🟡 manual; automated axe check TODO |

# Data Card - RaktSetu synthetic dataset

**Everything in the demo is synthetic.** No hospital, patient or donor data is used. Facility names are
fictional; coordinates are plausible points in Delhi NCT. Generator: `backend/app/sim/generator.py`;
loader: `backend/scripts/seed.py`. Fixed seed (42) -> fully reproducible (`make seed`).

## Network
- 1 state (Delhi NCT), 4 districts (New Delhi, South, North, East).
- 31 facilities: 8 large hospitals, 13 small hospitals (one **new, no history**: SH-13), 2 trauma centres,
  2 maternity hospitals, 6 blood banks.
- Components: red cells (RBC), platelets (PLT), fresh frozen plasma (FFP), cryoprecipitate (CRYO); 8 ABO/Rh groups -> 992 series.

## Demand process (ground truth)
Per facility x group x component x day, negative binomial (size 3, i.e. bursty) with mean:
`base(subtype, facility) x group share x component multiplier x weekday x season x festival x dengue x incident`
- Base RBC/day by subtype: large 16-26, small 2-5, trauma 12-16, maternity 5-7, bank 2-4.
- Group share: North-India mix (B+ 32%, O+ 31%, A+ 21%, AB+ 8%, negatives 1-2.5%). O- red cells get an
  emergency uplift (+5% of the facility's emergency share) because O- is released un-crossmatched.
- Component multipliers: PLT 0.35, FFP 0.28, CRYO 0.05 of RBC.
- Weekday: elective surgery weekdays (+10%), weekends lower; trauma centres busier on weekends.
- Season: +/-8% annual sine. Festivals (Diwali, Holi, New Year, Dussehra, Eid...) raise emergency demand
  within +/-3 days. Dengue index (peaks late Sep-Oct) multiplies platelet demand up to x3.2.
- Thalassemia: 145 patients across 4 sites, 2 RBC units every 21 days (cohort counts only, no identity) ->
  `scheduled_demand` + `consumption_daily.units_scheduled`.
- Incidents: 3 mass-casualty days in history (x2.2-x3 at large/trauma hospitals of one district).

## Supply and inventory
- Current stock: unit-level with collection and expiry dates; hospital cover RBC 2.5-7 days, PLT 2.2-3.8
  days, FFP 8-25, CRYO 10-40; blood banks hold district-level buffers.
- Demo scenarios (deliberate): LH-03 empty O- shelf; TC-01 and MC-01 one O- unit; LH-06 one B+ platelet;
  BB-02 holds 12 O- units expiring in ~5 days (rescue candidate); BB-03 holds 8 B+ platelets expiring in ~3 days.
- Live demo world (optional `world-tick` job): issues follow the same demand process, banks receive
  donations, hospitals get standing-order replenishment except protected demo series.

## Messiness injected on purpose
| Messiness | Amount | Where it shows |
|---|---|---|
| Duplicate submissions | ~3% of opening ledger events replayed (34 blocked) | idempotency key |
| Late-arriving rows | ~2% of history rows flagged `late` | Data Quality page |
| Silent facilities | SH-04 (now, 50 h), SH-08 (6 days, 2 months ago), BB-05 (4 days last month) | freshness badges, data-silent alert, NaN in panel |
| New facility | SH-13, no history | cold-start forecast, low confidence |
| Impossible entries | "C+", negative quantity, expiry before collection, 3500 mL "unit" | `rejected_entries` |
| Prompt-injection canary | SH-07 facility note | copilot treats it as data |

## Known limits
- Demand is stationary apart from the listed effects; real data will have drift, stock-outs censoring
  demand, and reporting artefacts not modelled here.
- Shelf-life and compatibility values are common practice, **not** validated against NACO/NBTC for any
  specific licence; they live in config tables for local confirmation.
- Results (docs/EVALUATION.md) show the method works on this generator; they are not clinical evidence.

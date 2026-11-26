# Five-minute demo script

Before: run `python -m scripts.smoke <URL>` 10 minutes ahead (wakes Neon, warms Cloud Run). Log in as
**Regional coordinator** in browser 1 and **Blood bank manager** in browser 2. Keep a recorded backup.

| Time | Show | Say |
|---|---|---|
| 0:00 | Command Centre: critical countdown card ticking | "Blood is perishable and local. Hospitals find out about shortages too late. RaktSetu shows time-to-stockout before it happens." |
| 0:40 | Risk Map: red marker (Charaka, B+ platelets), heat layer, routes | "This hospital has a 79% chance of running out of B+ platelets within 24 hours; confidence is high because its data is fresh." |
| 1:15 | Click marker -> Forecast Explorer: fan chart, expected-demand line, drivers | "Forecasts are probabilistic. For rare groups the median can say 0.3 a day while the expected demand is 0.8 - we plan on the mean." |
| 1:50 | Transfer Desk -> "Why this plan?" on South Regional -> Arogya O- move | "The optimizer chose this bank because its O- units expire in 5 days and arrive with over 90 hours left. It prevents a shortage and a discard." |
| 2:30 | Approve; browser 2 (bank) sees it under In progress; dispatch -> receive | "A human approves. Both inventories update; the bank sees it live." |
| 3:05 | Stress Test: click near Connaught Place, 120 casualties, run | "An incident. Watch which facilities break, and the plan that keeps trauma centres supplied." |
| 3:50 | Copilot in Hindi: "अगले 48 घंटों में किस रक्त समूह को सबसे अधिक खतरा है?" | "Gemini answers only from tool data; every number is checked against the source - open 'sources'." |
| 4:25 | Evaluation page | "On 90 days of synthetic data wastage fell 41% and unmet demand 42%, with 7.6x fewer alerts. Here are the limits too." |
| 4:50 | Architecture (docs/ARCHITECTURE.md section 5) | "FastAPI, Neon, React, Cloud Run, Firebase, Maps, Gemini, OR-Tools, BigQuery. Thank you." |

## UI acceptance run (Playwright or Antigravity browser agent)
Log in as coordinator; visit all 14 pages; open a "why" drawer; run the stress test; ask the copilot.
Expect zero console errors. Repeat as hospital user and confirm only one facility is visible in the matrix.
Last local run: 14/14 pages, 0 console errors.

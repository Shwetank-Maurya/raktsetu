# RaktSetu - project rules (for any coding agent: Antigravity, Cursor, Copilot, Codex...)

Read `docs/ARCHITECTURE.md` first. It is the single source of truth for how the system is built,
why, and where everything lives. `AGENTS.md` is a copy of these rules for non-Claude agents.

- Stack: FastAPI (py3.12), SQLAlchemy 2 async, Alembic, Postgres (Neon in prod, Docker locally),
  React + Vite + TS. Google: Gemini, Firebase (Auth, Firestore, Hosting, FCM, Analytics,
  Remote Config), Maps JS + Routes API, Calendar API, OR-Tools, Cloud Run, Cloud Scheduler,
  Secret Manager, Cloud Build, BigQuery (sandbox) + Looker Studio.
- Ledger is truth: never mutate `blood_units.status` outside `app/domain/ledger.py`.
  Every change appends an `inventory_events` row in the same transaction.
- Every write endpoint requires an `Idempotency-Key` header and writes an `audit_log` row.
- Never auto-substitute blood groups. Substitutions carry `needs_clinician_approval=true`.
- Gemini never computes numbers. It calls read-only tools; numbers come from tool JSON and
  `app/ai/guards.py` checks them. Every Gemini feature has a template fallback.
- Config over code: shelf life and compatibility live in `shelf_life_rules` / `compat_rules`
  tables (seeded from `app/domain/rules.py` defaults).
- All timestamps UTC in DB; display Asia/Kolkata in UI.
- Every Google integration must degrade gracefully when its credentials are missing
  (see the "Graceful degradation" table in docs/ARCHITECTURE.md).
- Every feature ships with tests. Run `make test` and `make lint` before commit.
- Small commits, conventional messages. Never commit secrets (.env is gitignored).
- App uses the pooled Neon URL (`DATABASE_URL`); Alembic uses the direct URL (`DATABASE_URL_DIRECT`).

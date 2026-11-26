# API contract

Generated from FastAPI's OpenAPI schema (`docs/openapi.json`, also served live at `/openapi.json` and `/docs`).
The frontend's typed client (`frontend/src/api/schema.d.ts`) is generated from the same schema: `npm run gen:api`.

Conventions: bearer token (Firebase ID token or demo token) on every `/api` call except health and demo login; `Idempotency-Key` header (8-100 chars) on every write; errors are `{"detail": ...}` with 401/403/404/409/422; timestamps ISO-8601 UTC.

| Method | Path | Summary | Tag |
|---|---|---|---|
| GET | `/api/healthz` | Healthz | meta |
| GET | `/healthz` | Healthz | meta |
| GET | `/api/readyz` | Readyz | meta |
| GET | `/readyz` | Readyz | meta |
| GET | `/api/meta` | Meta | meta |
| POST | `/api/auth/demo-login` | Demo Login | auth |
| GET | `/api/auth/me` | Me | auth |
| GET | `/api/regions` | Regions | registry |
| GET | `/api/facilities` | Facilities | registry |
| POST | `/api/inventory/events` | Post Event | inventory |
| GET | `/api/inventory/matrix` | Matrix | inventory |
| GET | `/api/inventory/expiring` | Expiring | inventory |
| GET | `/api/inventory/units` | Units | inventory |
| POST | `/api/reservations` | Create Reservation | inventory |
| POST | `/api/reservations/{reservation_id}/release` | Release Reservation | inventory |
| GET | `/api/risk` | Risk | risk |
| GET | `/api/kpis` | Kpis | risk |
| GET | `/api/map/risk` | Map Risk | risk |
| GET | `/api/map/heat` | Map Heat | risk |
| GET | `/api/forecasts/{facility_id}/{abo_rh}/{component}` | Forecast | risk |
| GET | `/api/availability/search` | Search | risk |
| GET | `/api/transfers` | List Transfers | transfers |
| POST | `/api/transfers` | Manual Request | transfers |
| POST | `/api/transfers/plan` | Plan | transfers |
| POST | `/api/transfers/{transfer_id}/approve` | Approve | transfers |
| POST | `/api/transfers/{transfer_id}/reject` | Reject | transfers |
| POST | `/api/transfers/{transfer_id}/dispatch` | Dispatch | transfers |
| POST | `/api/transfers/{transfer_id}/receive` | Receive | transfers |
| POST | `/api/transfers/{transfer_id}/cancel` | Cancel | transfers |
| GET | `/api/transfers/{transfer_id}/explain` | Explain | transfers |
| GET | `/api/alerts` | List Alerts | alerts |
| POST | `/api/alerts/{alert_id}/ack` | Ack | alerts |
| POST | `/api/push/subscribe` | Push Subscribe | alerts |
| POST | `/api/simulate/incident` | Incident | simulate |
| GET | `/api/simulate/assumptions` | Assumptions | simulate |
| PUT | `/api/simulate/assumptions` | Set Assumptions | simulate |
| POST | `/api/copilot/chat` | Chat | copilot |
| POST | `/api/donors/campaign/draft` | Campaign | donors |
| POST | `/api/register/extract` | Register Extract | register |
| POST | `/api/register/commit` | Register Commit | register |
| GET | `/api/eval` | Evaluation | evaluation |
| GET | `/api/data-quality` | Data Quality | evaluation |
| POST | `/internal/jobs/run-cycle` | Run Cycle Endpoint | internal |
| POST | `/internal/jobs/world-tick` | World Tick Endpoint | internal |
| POST | `/api/admin/run-cycle` | Admin Run Cycle | internal |

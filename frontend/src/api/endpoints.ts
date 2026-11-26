// One typed function per API endpoint. Pages call these instead of composing URLs, so paths,
// query strings and response types live in a single place.
import { api, enc } from "./client";
import type * as T from "./types";

const qs = (params: Record<string, string | number | boolean | null | undefined>) => {
  const p = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return p.length ? `?${p.map(([k, v]) => `${k}=${enc(String(v))}`).join("&")}` : "";
};

export const endpoints = {
  meta: () => api.get<T.Meta>("/api/meta"),
  regions: () => api.get<T.Region[]>("/api/regions"),
  facilities: () => api.get<T.Facility[]>("/api/facilities"),
  publicFacilities: () => api.get<T.PublicFacility[]>("/api/public/facilities"),

  kpis: () => api.get<T.Kpis>("/api/kpis"),
  risk: (params: { limit?: number; facility_id?: number | null; severity?: string } = {}) => api.get<T.RiskResponse>(`/api/risk${qs(params)}`),
  mapRisk: () => api.get<T.GeoCollection>("/api/map/risk"),
  mapHeat: (component?: string) => api.get<T.HeatResponse>(`/api/map/heat${qs({ component })}`),
  forecast: (facilityId: string, group: string, component: string) =>
    api.get<T.ForecastResponse>(`/api/forecasts/${facilityId}/${enc(group)}/${component}?history_days=90`),
  availability: (params: { abo_rh: string; component: string; radius_km?: number; facility_id?: number | null }) =>
    api.get<T.AvailabilityResponse>(`/api/availability/search${qs(params)}`),

  matrix: () => api.get<T.MatrixResponse>("/api/inventory/matrix"),
  expiring: (hours: number) => api.get<T.ExpiringResponse>(`/api/inventory/expiring${qs({ hours })}`),
  recordEvent: (body: Record<string, unknown>) => api.post<T.LedgerResult>("/api/inventory/events", body),

  transfers: (status: string, limit = 300) => api.get<T.Transfer[]>(`/api/transfers${qs({ status, limit })}`),
  explain: (id: number, lang: string) => api.get<T.Explanation>(`/api/transfers/${id}/explain${qs({ lang })}`),
  transferAction: (id: number, action: string, body: Record<string, unknown> = {}) => api.post<T.Transfer>(`/api/transfers/${id}/${action}`, body),
  plan: () => api.post<{ stats: Record<string, number> }>("/api/transfers/plan", { include_substitutes: true }),

  alerts: (params: { status?: string; limit?: number } = {}) => api.get<T.Alert[]>(`/api/alerts${qs(params)}`),
  ackAlert: (id: number) => api.post<{ id: number; status: string }>(`/api/alerts/${id}/ack`, {}),

  incidentAssumptions: () => api.get<T.IncidentAssumptions>("/api/simulate/assumptions"),
  simulateIncident: (body: Record<string, unknown>) => api.read<T.IncidentResult>("/api/simulate/incident", body),
  copilot: (body: { message: string; language: string; history: { role: string; text: string }[] }) => api.read<T.CopilotResponse>("/api/copilot/chat", body),
  campaign: (body: Record<string, unknown>) => api.read<T.CampaignDraft>("/api/donors/campaign/draft", body),
  registerExtract: (form: FormData) => api.upload<T.RegisterExtract>("/api/register/extract", form),
  registerCommit: (body: { facility_id: number; rows: Partial<T.RegisterRow>[] }) => api.post<{ committed_rows: number; units: number }>("/api/register/commit", body),

  evaluation: () => api.get<T.EvalResponse>("/api/eval"),
  dataQuality: () => api.get<T.DataQualityResponse>("/api/data-quality"),

  myAccessRequest: () => api.get<T.AccessRequest | null>("/api/access-requests/mine"),
  accessRequests: (status: string) => api.get<T.AccessRequest[]>(`/api/access-requests${qs({ status })}`),
  requestAccess: (body: { name: string; requested_role: string; facility_id: number; note: string | null }) => api.post<T.AccessRequest>("/api/access-requests", body),
  decideAccess: (id: number, action: "approve" | "reject") => api.post<T.AccessRequest>(`/api/access-requests/${id}/${action}`, {}),
};

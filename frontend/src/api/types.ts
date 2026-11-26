// Response shapes of the RaktSetu API (mirrors the FastAPI handlers in backend/app/api/*).
// Request bodies are typed from the generated OpenAPI schema (./schema.d.ts) where available.

export type Severity = "critical" | "high" | "medium" | "low";
export type AlertSeverity = "critical" | "high" | "warning" | "info";
export type AboRh = "O-" | "O+" | "A-" | "A+" | "B-" | "B+" | "AB-" | "AB+";
export type ComponentCode = "RBC" | "PLT" | "FFP" | "CRYO";
export type Role = "hospital_user" | "bank_manager" | "regional_coordinator" | "admin" | "pending";

export interface Facility {
  id: number; code: string; name: string; type: "hospital" | "blood_bank"; subtype: string; region_id: number;
  lat: number; lng: number; beds: number; active: boolean; is_trauma_centre: boolean; freshness_h: number | null; in_scope: boolean;
}

export interface Region { id: number; name: string; parent_id: number | null; level: "state" | "district"; lat: number | null; lng: number | null }

export interface RiskItem {
  facility_id: number; facility_name: string; facility_code: string; region_id: number; abo_rh: AboRh; component: ComponentCode;
  usable_units: number; p_stockout_24: number; p_stockout_48: number; p_stockout_72: number; tts_p10: number | null; tts_p50: number | null;
  days_cover: number; expected_wastage: number; risk_score: number; severity: Severity; confidence: number; stale: boolean;
  lead_time_h: number; model_used: string; event_mode: boolean; as_of: string;
}
export interface RiskResponse { as_of: string | null; count: number; items: RiskItem[] }

export interface Kpis {
  as_of: string | null; facilities: number; severity_counts: Partial<Record<Severity, number>>; open_alerts: number;
  pending_proposals: number; wastage_avoided_units: number; expected_wastage_units: number; resilience_score: number | null;
  regional_resilience: Record<string, number>; stale_facilities: { id: number; name: string; hours: number }[];
  critical_countdowns: RiskItem[];
}

export interface Alert {
  id: number; kind: string; severity: AlertSeverity; status: "open" | "ack" | "resolved"; message: string;
  facility_id: number | null; abo_rh: AboRh | null; component: ComponentCode | null; details: Record<string, unknown> | null;
  first_seen: string; last_seen: string; escalated_at: string | null; acknowledged_by: string | null;
}

export interface TransferReason {
  destination?: { severity?: Severity; p_stockout_24h?: number; tts_p50_h?: number | null; usable_before?: number; need_units?: number };
  source?: { usable_before?: number; safety_stock?: number; usable_after?: number; expected_wastage?: number };
  saves?: { shortage_units: number; wastage_units: number };
  constraints?: Record<string, unknown>;
  [key: string]: unknown;
}
export type TransferStatus = "proposed" | "approved" | "dispatched" | "received" | "rejected" | "cancelled" | "superseded" | "expired";
export interface Transfer {
  id: number; plan_id: string | null; kind: string; status: TransferStatus;
  from_facility_id: number; from_name: string | null; from_lat: number | null; from_lng: number | null;
  to_facility_id: number; to_name: string | null; to_lat: number | null; to_lng: number | null;
  abo_rh: AboRh; component: ComponentCode; requested_for_abo_rh: AboRh | null; quantity: number; unit_ids: string[];
  eta_minutes: number; distance_km: number; eta_source: string; min_life_on_arrival_h: number;
  needs_clinician_approval: boolean; flagged_for_review: boolean; reason: TransferReason;
  created_by: string; approved_by: string | null; created_at: string; updated_at: string; dispatched_at: string | null; received_at: string | null;
}
export interface Explanation { summary: string; bullets: string[]; fallback: boolean; provider?: string }

export interface MatrixCell { usable: number; available?: number; reserved?: number; quarantined?: number; in_transit?: number }
export interface MatrixRow { facility_id: number; code: string; name: string; type: string; region_id: number; freshness_h: number | null; cells: Record<string, MatrixCell> }
export interface MatrixResponse { as_of: string; facilities: MatrixRow[] }

export interface AvailabilityResult {
  facility_id: number; facility_name: string; facility_code: string; type: string; abo_rh: AboRh; component: ComponentCode; units: number;
  exact_match: boolean; needs_clinician_approval: boolean; eta_minutes: number; distance_km: number;
  earliest_expiry_h: number; latest_expiry_h: number; freshness_h: number; lat: number; lng: number;
}
export interface AvailabilityResponse { as_of: string; query: Record<string, unknown>; results: AvailabilityResult[] }

export interface ExpiryGroup { facility_id: number; facility_name: string; abo_rh: AboRh; component: ComponentCode; units: number; earliest_expiry_h: number; unit_ids: string[] }
export interface ExpiringResponse { as_of: string; hours: number; buckets: Record<string, number>; groups: ExpiryGroup[] }

export interface ForecastPoint { date: string; q10: number; q50: number; q90: number; mean: number; scheduled: number }
export interface ForecastResponse {
  facility_id: number; abo_rh: AboRh; component: ComponentCode;
  history: { date: string; units: number; emergency: number; scheduled: number; event: boolean; quality: string }[];
  forecast: ForecastPoint[]; model: string | null; model_version: string | null; drivers: { kind: string; label: string; weight: number }[];
  risk: Pick<RiskItem, "p_stockout_24" | "p_stockout_48" | "p_stockout_72" | "tts_p10" | "tts_p50" | "usable_units" | "severity" | "confidence" | "days_cover"> | null;
}

export interface GeoFeature {
  type: "Feature"; geometry: { type: "Point"; coordinates: [number, number] };
  properties: { id: number; code: string; name: string; type: string; subtype: string; region_id: number; severity: Severity;
    risk_score: number; worst_series: string | null; tts_p50: number | null; p_stockout_24: number; freshness_h: number | null };
}
export interface GeoCollection { type: "FeatureCollection"; features: GeoFeature[] }
export interface HeatResponse { points: { lat: number; lng: number; weight: number }[] }

export interface IncidentAssumptions { severity_mix: Record<string, number>; units_per_casualty: Record<string, Record<string, number>>; note: string; [k: string]: unknown }
export interface IncidentResult {
  assumptions: IncidentAssumptions; total_extra_units: Record<ComponentCode, number>; facilities_breaking: number;
  affected: { facility_id: number; name: string; abo_rh: AboRh; component: ComponentCode; before: Severity; after: Severity; p_stockout_24: number; tts_p50: number | null }[];
  plan: { from_name: string; to_name: string; abo_rh: AboRh; component: ComponentCode; quantity: number; eta_minutes: number; needs_clinician_approval: boolean;
    from_lat: number; from_lng: number; to_lat: number; to_lng: number }[];
  unmet: { facility_id: number; abo_rh: AboRh; component: ComponentCode; unmet_units: number }[];
}

export interface CopilotResponse { answer: string; tools_used: string[]; tool_payloads: unknown[]; grounded: boolean; fallback: boolean; provider?: string; as_of: string | null }
export interface CampaignDraft {
  facility: string; abo_rh: AboRh; component: ComponentCode; language: string; eligible_donors: number; template: string; fallback: boolean;
  sending: string; privacy: string; previews: { donor_id: number; first_name: string; distance_km: number; message: string }[];
}

export interface RegisterRow {
  row?: number; abo_rh: AboRh; component: ComponentCode; quantity: number; donation_id?: string; collected_on?: string; expires_on?: string;
  confidence?: Record<string, number>; low_confidence_fields: string[]; issues: string[]; blocks_commit?: boolean;
}
export interface RegisterExtract { facility_id: number; rows: RegisterRow[]; requires_review: boolean; can_commit: boolean }

export interface JobRun { id: string; kind: string; status: string; started_at: string; finished_at: string | null;
  stats: { duration_s?: number; risk_series?: number; trigger?: string; plan?: { proposals?: number } } | null }
export interface BacktestMetric { wape: number; pinball: number; coverage80_raw: number; n: number }
export interface EvalResponse {
  backtest?: { overall: Record<string, number | string | null> & { wape_baseline: number; wape_raktsetu: number; wape_improvement_pct: number;
    pinball50_baseline: number; pinball50_raktsetu: number; coverage80_calibrated: number; coverage80_raw_holdout: number; mean_bias_ratio?: number; coverage_note: string };
    metrics: Record<string, Record<string, BacktestMetric>>; chosen: Record<string, string>; conformal: Record<string, number> };
  replay?: { days: number; method: string; improvement: { wastage_reduction_pct: number; unmet_reduction_pct: number; stockout_days_reduction_pct: number };
    policy_a: ReplayPolicy; policy_b: ReplayPolicy };
  job_runs: JobRun[];
}
export interface ReplayPolicy { wasted: number; unmet: number; stockout_days: number; fulfilment_pct: number; alerts: number; alert_recall_48h: number; alert_precision: number }

export interface DataQualityResponse {
  facilities: { id: number; code: string; name: string; active: boolean; freshness_h: number | null; reported_days_30: number; late_rows_30: number; event_days_30: number }[];
  rejected_entries: { id: number; facility_id: number | null; source: string; reason: string; payload: unknown; created_at: string }[];
  recent_audit: { actor: string; role: string; action: string; entity: string; entity_id: string; ts: string }[];
}

export interface AccessRequest {
  id: number; uid: string; email: string | null; name: string; requested_role: "hospital_user" | "bank_manager";
  facility_id: number; facility_name: string | null; facility_code: string | null; note: string | null;
  status: "pending" | "approved" | "rejected"; decided_by: string | null; decision_note: string | null; created_at: string; decided_at: string | null;
}
export interface PublicFacility { id: number; code: string; name: string; type: "hospital" | "blood_bank"; district: string | null }

export interface Meta {
  env: string; data: string; disclaimer: string;
  integrations: { gemini: { enabled: boolean; model: string }; groq: { enabled: boolean }; firebase_auth: boolean; demo_auth: boolean;
    firestore_live_feed: boolean; fcm_push: boolean; routes_api: boolean; google_calendar: boolean; bigquery_export: boolean; or_tools: boolean };
}

export interface LedgerResult { unit_ids: string[]; count: number; event_id: number; duplicate: boolean }

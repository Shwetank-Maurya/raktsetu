// Public, DB-backed network facts (GET /api/public/summary). Anything the UI states about the
// network, the engine or the clinical rules should come from here instead of being hard-coded.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export type PublicSummary = {
  facilities: number;
  series_monitored: number;
  severity_counts: Record<string, number>;
  as_of: string | null;
  last_cycle: string | null;
  forecast?: { wape_improvement_pct: number | null; coverage80: number | null };
  replay?: { wastage_reduction_pct: number; unmet_reduction_pct: number; stockout_days_reduction_pct: number; days: number; alerts_a: number; alerts_b: number };
  network: { by_subtype: Record<string, number>; region: string | null; districts: string[]; center: [number, number] | null; blood_groups: number; components: number };
  rules: Record<string, { shelf_life_h: number; min_usable_h: number; min_life_on_arrival_h: number; max_transit_h: number; storage: string }>;
  engine: { risk_paths: number; horizon_h: number };
  demo_roles: Record<string, { role: string; title: string; scope: string; scope_kind: "facility" | "region" }>;
};

export const usePublicSummary = () =>
  useQuery<PublicSummary>({ queryKey: ["public-summary"], queryFn: () => api.get("/api/public/summary"), staleTime: 60_000 });

const n = (x: number | null | undefined, digits = 0) =>
  x == null ? undefined : x.toLocaleString("en-IN", { maximumFractionDigits: digits });

/** Values available to article text as {{key}} tokens. */
export function contentVars(d?: PublicSummary): Record<string, string | undefined> {
  if (!d) return {};
  return {
    facilities: n(d.facilities),
    risk_paths: n(d.engine?.risk_paths),
    horizon_days: n(d.engine ? d.engine.horizon_h / 24 : undefined),
    coverage80_pct: d.forecast?.coverage80 != null ? `${n(d.forecast.coverage80 * 100, 1)}%` : undefined,
    wape_improvement_pct: d.forecast?.wape_improvement_pct != null ? `${n(d.forecast.wape_improvement_pct, 1)}%` : undefined,
    wastage_reduction_pct: d.replay ? `${n(d.replay.wastage_reduction_pct, 1)}%` : undefined,
    unmet_reduction_pct: d.replay ? `${n(d.replay.unmet_reduction_pct, 1)}%` : undefined,
    replay_days: n(d.replay?.days),
    rbc_arrival_h: n(d.rules?.RBC?.min_life_on_arrival_h),
    plt_arrival_h: n(d.rules?.PLT?.min_life_on_arrival_h),
    plt_min_usable_h: n(d.rules?.PLT?.min_usable_h),
    region: d.network?.region ?? undefined,
    districts: n(d.network?.districts.length),
  };
}

/** Replace {{key}} or {{key|fallback}} tokens; unknown keys use the fallback (or stay readable). */
export function fill(text: string, vars: Record<string, string | undefined>): string {
  return text.replace(/\{\{(\w+)(?:\|([^}]*))?\}\}/g, (_, k: string, fb?: string) => vars[k] ?? fb ?? k);
}

const LABEL: Record<string, [string, string]> = {
  large: ["large hospital", "large hospitals"], small: ["smaller hospital", "smaller hospitals"],
  trauma: ["trauma centre", "trauma centres"], maternity: ["maternity hospital", "maternity hospitals"],
  bank: ["blood bank", "blood banks"],
};

/** "8 large hospitals, 13 smaller hospitals, ... and 6 blood banks across 4 districts" */
export function describeNetwork(d?: PublicSummary): string | null {
  if (!d?.network) return null;
  const parts = Object.entries(d.network.by_subtype)
    .sort(([a], [b]) => Object.keys(LABEL).indexOf(a) - Object.keys(LABEL).indexOf(b))
    .map(([k, v]) => `${v} ${(LABEL[k] ?? [k, k])[v === 1 ? 0 : 1]}`);
  if (!parts.length) return null;
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
  const nd = d.network.districts.length;
  return `${list}${nd ? ` across ${nd} district${nd === 1 ? "" : "s"}` : ""}`;
}

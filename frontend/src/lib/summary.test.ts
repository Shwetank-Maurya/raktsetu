import { describe, expect, it } from "vitest";
import { contentVars, describeNetwork, fill, type PublicSummary } from "./summary";

const summary = {
  facilities: 31, series_monitored: 856, severity_counts: { critical: 1 }, as_of: null, last_cycle: null,
  forecast: { wape_improvement_pct: 29.8, coverage80: 0.803 },
  replay: { wastage_reduction_pct: 40.9, unmet_reduction_pct: 42.2, stockout_days_reduction_pct: 23.7, days: 90, alerts_a: 15785, alerts_b: 2080 },
  network: { by_subtype: { bank: 6, large: 8, small: 1 }, region: "Delhi NCT", districts: ["A", "B", "C", "D"], center: null, blood_groups: 8, components: 4 },
  rules: { RBC: { shelf_life_h: 1008, min_usable_h: 24, min_life_on_arrival_h: 72, max_transit_h: 6, storage: "2-6 C" },
           PLT: { shelf_life_h: 120, min_usable_h: 12, min_life_on_arrival_h: 60, max_transit_h: 4, storage: "20-24 C" } },
  engine: { risk_paths: 2000, horizon_h: 168 },
  demo_roles: {},
} satisfies PublicSummary;

describe("fill", () => {
  it("replaces known tokens and uses fallbacks for unknown ones", () => {
    expect(fill("{{a}} and {{b|default}}", { a: "x" })).toBe("x and default");
  });
  it("keeps the token name readable when there is no value or fallback", () => {
    expect(fill("{{missing}}", {})).toBe("missing");
  });
});

describe("contentVars", () => {
  it("formats live values for article text", () => {
    const v = contentVars(summary);
    expect(v.risk_paths).toBe("2,000");
    expect(v.coverage80_pct).toBe("80.3%");
    expect(v.wastage_reduction_pct).toBe("40.9%");
    expect(v.rbc_arrival_h).toBe("72");
    expect(v.horizon_days).toBe("7");
  });
  it("returns no values before data loads", () => {
    expect(contentVars(undefined)).toEqual({});
  });
});

describe("describeNetwork", () => {
  it("orders facility types, pluralises and counts districts", () => {
    expect(describeNetwork(summary)).toBe("8 large hospitals, 1 smaller hospital and 6 blood banks across 4 districts");
  });
  it("returns null without data", () => {
    expect(describeNetwork(undefined)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { contentVars } from "../lib/summary";
import { ARTICLES, bySlug } from "./articles";

// Every {{token}} used in article text must be a key that contentVars() can fill.
const KNOWN = Object.keys(contentVars({
  facilities: 1, series_monitored: 1, severity_counts: {}, as_of: null, last_cycle: null,
  forecast: { wape_improvement_pct: 1, coverage80: 0.8 },
  replay: { wastage_reduction_pct: 1, unmet_reduction_pct: 1, stockout_days_reduction_pct: 1, days: 1, alerts_a: 1, alerts_b: 1 },
  network: { by_subtype: {}, region: "R", districts: [], center: null, blood_groups: 8, components: 4 },
  rules: { RBC: { shelf_life_h: 1, min_usable_h: 1, min_life_on_arrival_h: 1, max_transit_h: 1, storage: "" },
           PLT: { shelf_life_h: 1, min_usable_h: 1, min_life_on_arrival_h: 1, max_transit_h: 1, storage: "" } },
  engine: { risk_paths: 1, horizon_h: 24 }, demo_roles: {},
}));

describe("articles", () => {
  it("have unique slugs that resolve", () => {
    const slugs = ARTICLES.map((a) => a.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    slugs.forEach((s) => expect(bySlug(s)?.slug).toBe(s));
  });

  it("only use template tokens the live summary can provide", () => {
    const text = JSON.stringify(ARTICLES.map((a) => a.body));
    const tokens = [...text.matchAll(/\{\{(\w+)/g)].map((m) => m[1]);
    expect(tokens.length).toBeGreaterThan(0);
    tokens.forEach((t) => expect(KNOWN).toContain(t));
  });

  it("have dates and non-empty bodies", () => {
    ARTICLES.forEach((a) => {
      expect(Number.isNaN(Date.parse(a.date))).toBe(false);
      expect(a.body.length).toBeGreaterThan(0);
    });
  });
});

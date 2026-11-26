import { describe, expect, it } from "vitest";
import { hrs, pct } from "./format";

describe("pct", () => {
  it("rounds probabilities to whole percentages", () => {
    expect(pct(0.786)).toBe("79%");
    expect(pct(0)).toBe("0%");
  });
  it("shows a dash for missing values", () => {
    expect(pct(null)).toBe("-");
    expect(pct(undefined)).toBe("-");
  });
});

describe("hrs", () => {
  it("uses hours under two days and days beyond", () => {
    expect(hrs(0.5)).toBe("< 1 h");
    expect(hrs(26.4)).toBe("26 h");
    expect(hrs(60)).toBe("2.5 days");
  });
  it("treats no stockout in the horizon as beyond a week", () => {
    expect(hrs(null)).toBe("> 7 days");
  });
});

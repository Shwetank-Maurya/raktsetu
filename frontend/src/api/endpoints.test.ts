import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./client";
import { endpoints } from "./endpoints";

// The deployment may prefix requests with VITE_API_BASE; assert on the path only.
const path = (url: string) => url.replace(/^https?:\/\/[^/]+/, "");

function mockFetch(status = 200, body: unknown = {}) {
  const fn = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("endpoints", () => {
  it("builds query strings and drops empty parameters", async () => {
    const f = mockFetch(200, { items: [] });
    await endpoints.risk({ limit: 8, facility_id: null });
    expect(path(f.mock.calls[0][0])).toBe("/api/risk?limit=8");
  });

  it("URL-encodes blood groups in paths", async () => {
    const f = mockFetch(200, { history: [], forecast: [] });
    await endpoints.forecast("3", "AB+", "PLT");
    expect(path(f.mock.calls[0][0])).toBe("/api/forecasts/3/AB%2B/PLT?history_days=90");
  });

  it("sends a unique Idempotency-Key with every write", async () => {
    const f = mockFetch(200, { count: 1 });
    await endpoints.recordEvent({ type: "receive" });
    await endpoints.recordEvent({ type: "receive" });
    const keys = f.mock.calls.map((c) => (c[1]?.headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys[0]).not.toBe(keys[1]);
  });

  it("does not send an Idempotency-Key on reads", async () => {
    const f = mockFetch(200, {});
    await endpoints.kpis();
    expect((f.mock.calls[0][1]?.headers as Record<string, string>)["Idempotency-Key"]).toBeUndefined();
  });

  it("surfaces API errors with status and detail", async () => {
    mockFetch(403, { detail: "facility outside your scope" });
    const err = await endpoints.matrix().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(403);
    expect((err as ApiError).message).toBe("facility outside your scope");
  });
});

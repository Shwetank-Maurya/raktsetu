// Thin typed fetch wrapper. Types come from src/api/schema.d.ts, generated from FastAPI's OpenAPI
// schema (`npm run gen:api`), so frontend and backend cannot silently drift apart.
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type IncidentIn = Schemas["IncidentIn"];
export type CampaignIn = Schemas["CampaignIn"];

// Same-origin by default (Firebase Hosting rewrites /api/** to Cloud Run). Option A (Render) sets VITE_API_BASE.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
const TOKEN_KEY = "raktsetu.token";
let tokenProvider: (() => Promise<string | null>) | null = null;

export function setTokenProvider(fn: (() => Promise<string | null>) | null) {
  tokenProvider = fn;
}
export const getStoredToken = () => sessionStorage.getItem(TOKEN_KEY);
export const storeToken = (t: string | null) => (t ? sessionStorage.setItem(TOKEN_KEY, t) : sessionStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

async function request<T>(method: string, path: string, body?: unknown, opts: { idempotent?: boolean; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = (tokenProvider && (await tokenProvider())) || getStoredToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  // Every write carries an Idempotency-Key so retries and double-clicks never double-count.
  if (opts.idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
  let payload: BodyInit | undefined;
  if (opts.form) payload = opts.form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, { method, headers, body: payload });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? data ?? res.statusText);
  return data as T;
}

export const api = {
  get: <T = any>(path: string) => request<T>("GET", path),
  post: <T = any>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}, { idempotent: true }),
  put: <T = any>(path: string, body?: unknown) => request<T>("PUT", path, body, { idempotent: true }),
  read: <T = any>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}), // read-only POST (copilot, simulate)
  upload: <T = any>(path: string, form: FormData) => request<T>("POST", path, undefined, { form }),
};

export const enc = (g: string) => encodeURIComponent(g);

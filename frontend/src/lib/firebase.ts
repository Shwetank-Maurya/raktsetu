// Firebase: Auth (role claims), Firestore live feed, Cloud Messaging push, Analytics and
// Remote Config feature flags. Everything is optional: with no VITE_FIREBASE_* config the app
// falls back to demo login and polling.
import { initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import { getFirestore, type Firestore } from "firebase/firestore";

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

export const firebaseEnabled = Boolean(cfg.apiKey && cfg.projectId);
export const app: FirebaseApp | null = firebaseEnabled ? initializeApp(cfg) : null;
export const auth: Auth | null = app ? getAuth(app) : null;
export const db: Firestore | null = app ? getFirestore(app) : null;

export const DEFAULT_FLAGS = { stress_test: true, register_ocr: true, donor_campaigns: true, copilot: true };
export type Flags = typeof DEFAULT_FLAGS;

export async function loadFlags(): Promise<Flags> {
  if (!app) return DEFAULT_FLAGS;
  try {
    const rc = await import("firebase/remote-config");
    const r = rc.getRemoteConfig(app);
    r.settings.minimumFetchIntervalMillis = 10 * 60 * 1000;
    r.defaultConfig = Object.fromEntries(Object.entries(DEFAULT_FLAGS).map(([k, v]) => [k, String(v)]));
    await rc.fetchAndActivate(r);
    return Object.fromEntries(Object.keys(DEFAULT_FLAGS).map((k) => [k, rc.getValue(r, k).asBoolean()])) as Flags;
  } catch {
    return DEFAULT_FLAGS;
  }
}

export async function track(event: string, params: Record<string, unknown> = {}) {
  if (!app || !cfg.measurementId) return;
  try {
    const an = await import("firebase/analytics");
    if (await an.isSupported()) an.logEvent(an.getAnalytics(app), event, params);
  } catch {
    /* analytics is best-effort */
  }
}

export async function enablePush(regionId: number | null): Promise<string> {
  if (!app) return "Firebase not configured";
  const vapid = import.meta.env.VITE_FIREBASE_VAPID_KEY;
  try {
    const m = await import("firebase/messaging");
    if (!(await m.isSupported())) return "Push not supported in this browser";
    const reg = await navigator.serviceWorker.register(`/firebase-messaging-sw.js?config=${encodeURIComponent(JSON.stringify(cfg))}`);
    const tokenStr = await m.getToken(m.getMessaging(app), { vapidKey: vapid, serviceWorkerRegistration: reg });
    if (!tokenStr) return "Permission denied";
    const { api } = await import("../api/client");
    const r = await api.read<{ subscribed: boolean; topic?: string; reason?: string }>("/api/push/subscribe", { token: tokenStr });
    return r.subscribed ? `Push enabled (topic ${r.topic}, region ${regionId ?? 1})` : `Push not enabled: ${r.reason}`;
  } catch (e) {
    return `Push unavailable: ${(e as Error).message}`;
  }
}

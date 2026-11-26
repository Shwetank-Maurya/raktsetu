import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity, AlertTriangle, BarChart3, Bot, Camera, ClipboardList, Database, Droplet, FlaskConical, Grid3x3, HeartHandshake,
  Map as MapIcon, PackagePlus, Timer, Truck,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../lib/auth";
import { useI18n, type Key } from "../lib/i18n";
import { useLiveFeed } from "../lib/live";

const NAV: { to: string; key: Key; icon: typeof Activity; roles?: string[] }[] = [
  { to: "/", key: "command", icon: Activity },
  { to: "/map", key: "map", icon: MapIcon },
  { to: "/matrix", key: "matrix", icon: Grid3x3 },
  { to: "/expiry", key: "expiry", icon: Timer },
  { to: "/forecast", key: "forecast", icon: BarChart3 },
  { to: "/transfers", key: "transfers", icon: Truck },
  { to: "/alerts", key: "alerts", icon: AlertTriangle },
  { to: "/inventory", key: "inventory", icon: PackagePlus, roles: ["bank_manager", "hospital_user", "regional_coordinator", "admin"] },
  { to: "/stress", key: "stress", icon: FlaskConical, roles: ["regional_coordinator", "admin"] },
  { to: "/copilot", key: "copilot", icon: Bot },
  { to: "/donors", key: "donors", icon: HeartHandshake, roles: ["bank_manager", "regional_coordinator", "admin"] },
  { to: "/register", key: "register", icon: Camera, roles: ["bank_manager", "hospital_user", "admin"] },
  { to: "/evaluation", key: "eval", icon: ClipboardList },
  { to: "/quality", key: "quality", icon: Database },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const { live, lastEvent } = useLiveFeed();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api.get("/api/meta"), staleTime: 300_000 });
  const integ = meta.data?.integrations ?? {};
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-800">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:bg-white focus:p-2">Skip to content</a>
      <nav aria-label="Main" className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 px-4 py-4">
          <Droplet className="text-rose-700" fill="currentColor" />
          <div>
            <div className="font-bold leading-tight text-rose-800">RaktSetu</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">blood bridge</div>
          </div>
        </div>
        <ul className="flex-1 space-y-0.5 px-2">
          {NAV.filter((n) => !n.roles || n.roles.includes(user?.role ?? "")).map((n) => (
            <li key={n.to}>
              <NavLink to={n.to} end={n.to === "/"} className={({ isActive }) => clsx("flex items-center gap-2 rounded-lg px-3 py-2 text-sm", isActive ? "bg-rose-50 font-semibold text-rose-800" : "text-slate-600 hover:bg-slate-100")}>
                <n.icon size={16} aria-hidden /> {t(n.key)}
              </NavLink>
            </li>
          ))}
        </ul>
        <div className="space-y-1 border-t border-slate-200 p-3 text-[11px] text-slate-500">
          <div className="font-semibold text-slate-600">Google stack status</div>
          {[["gemini", integ.gemini?.enabled], ["firebase auth", integ.firebase_auth], ["firestore live", integ.firestore_live_feed],
            ["routes api", integ.routes_api], ["calendar api", integ.google_calendar], ["bigquery", integ.bigquery_export], ["or-tools", integ.or_tools]].map(([k, v]) => (
            <div key={String(k)} className="flex justify-between"><span>{String(k)}</span><span className={v ? "text-emerald-700" : "text-slate-400"}>{v ? "on" : "fallback"}</span></div>
          ))}
        </div>
      </nav>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-900">{t("synthetic")}</span>
            <span className="hidden text-slate-500 lg:inline">{t("decision")}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className={clsx("flex items-center gap-1 text-xs", live ? "text-emerald-700" : "text-slate-500")} title={lastEvent ?? ""}>
              <span className={clsx("h-2 w-2 rounded-full", live ? "animate-pulse bg-emerald-500" : "bg-slate-400")} /> {live ? "Firestore live" : "polling"}
            </span>
            <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="rounded border border-slate-300 px-2 py-0.5 text-xs" aria-label="Toggle language">
              {lang === "en" ? "हिन्दी" : "English"}
            </button>
            <span className="hidden text-xs text-slate-600 sm:inline">{user?.name} · <b>{user?.role.replace("_", " ")}</b></span>
            <button onClick={logout} className="text-xs text-rose-700 hover:underline">{t("logout")}</button>
          </div>
        </header>
        <nav aria-label="Mobile" className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-2 py-1 md:hidden">
          {NAV.filter((n) => !n.roles || n.roles.includes(user?.role ?? "")).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) => clsx("whitespace-nowrap rounded px-2 py-1 text-xs", isActive ? "bg-rose-50 text-rose-800" : "text-slate-600")}>{t(n.key)}</NavLink>
          ))}
        </nav>
        <main id="main" className="flex-1 p-4 lg:p-6"><Outlet /></main>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity, BarChart3, Bell, Bot, Camera, ClipboardCheck, Database, Droplet, FileText, FlaskConical, Grid3x3, HeartHandshake,
  LogOut, Map as MapIcon, Menu, PackagePlus, Timer, Truck, UserPlus, X,
} from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../lib/auth";
import { useI18n, type Key } from "../lib/i18n";
import { useLiveFeed } from "../lib/live";

type Item = { to: string; key: Key; icon: typeof Activity; roles?: string[] };
const GROUPS: { label: string; items: Item[] }[] = [
  { label: "Monitor", items: [
    { to: "/", key: "command", icon: Activity }, { to: "/map", key: "map", icon: MapIcon },
    { to: "/alerts", key: "alerts", icon: Bell },
  ] },
  { label: "Inventory", items: [
    { to: "/matrix", key: "matrix", icon: Grid3x3 }, { to: "/expiry", key: "expiry", icon: Timer },
    { to: "/inventory", key: "inventory", icon: PackagePlus, roles: ["bank_manager", "hospital_user", "regional_coordinator", "admin"] },
  ] },
  { label: "Plan", items: [
    { to: "/forecast", key: "forecast", icon: BarChart3 }, { to: "/transfers", key: "transfers", icon: Truck },
    { to: "/stress", key: "stress", icon: FlaskConical, roles: ["regional_coordinator", "admin"] },
  ] },
  { label: "Assist", items: [
    { to: "/copilot", key: "copilot", icon: Bot },
    { to: "/donors", key: "donors", icon: HeartHandshake, roles: ["bank_manager", "regional_coordinator", "admin"] },
    { to: "/register", key: "register", icon: Camera, roles: ["bank_manager", "hospital_user", "admin"] },
  ] },
  { label: "Insights", items: [
    { to: "/evaluation", key: "eval", icon: ClipboardCheck }, { to: "/quality", key: "quality", icon: Database },
    { to: "/articles", key: "articles", icon: FileText },
  ] },
  { label: "Admin", items: [
    { to: "/access", key: "access", icon: UserPlus, roles: ["regional_coordinator", "admin"] },
  ] },
];

export function Logo({ light = false, compact = false }: { light?: boolean; compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="RaktSetu home">
      <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-white"><Droplet size={15} fill="currentColor" /></span>
      {!compact && <span className={clsx("text-[15px] font-semibold tracking-tight", light ? "text-white" : "text-ink")}>RaktSetu</span>}
    </Link>
  );
}

const ROLE_LABEL: Record<string, string> = { regional_coordinator: "Coordinator", bank_manager: "Blood bank", hospital_user: "Hospital", admin: "Admin" };

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const initials = (user?.name || "U").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className="flex h-full flex-col">
      <div className="px-4 py-4"><Logo /></div>
      <nav aria-label="Main" className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {GROUPS.map((g) => {
          const items = g.items.filter((i) => !i.roles || i.roles.includes(user?.role ?? ""));
          if (!items.length) return null;
          return (
            <div key={g.label}>
              <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-faint">{g.label}</div>
              <ul className="space-y-0.5">
                {items.map((i) => (
                  <li key={i.to}>
                    <NavLink to={i.to} end={i.to === "/"} onClick={onNavigate}
                      className={({ isActive }) => clsx("flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm",
                        isActive ? "bg-white font-medium text-ink shadow-[0_0_0_1px_var(--color-line)]" : "text-body hover:bg-white/70 hover:text-ink")}>
                      <i.icon size={15} className="shrink-0 text-muted" aria-hidden /> {t(i.key)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </nav>
      <div className="border-t border-line p-3">
        <div className="flex items-center gap-2.5 rounded-md px-1.5 py-1.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-white">{initials}</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-ink">{user?.name || "Signed in"}</div>
            <div className="truncate text-xs text-muted">{ROLE_LABEL[user?.role ?? ""] ?? user?.role}{user?.auth === "firebase" ? " · Firebase" : ""}</div>
          </div>
          <button onClick={logout} title={t("logout")} aria-label={t("logout")} className="rounded-md p-1.5 text-muted hover:bg-white hover:text-ink"><LogOut size={15} /></button>
        </div>
      </div>
    </div>
  );
}

export default function Layout() {
  const { lang, setLang } = useI18n();
  const { live } = useLiveFeed();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: () => api.get("/api/kpis"), staleTime: 30_000 });
  const openAlerts = kpis.data?.open_alerts ?? 0;
  return (
    <div className="min-h-screen bg-canvas">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[1001] focus:rounded focus:bg-white focus:p-2">Skip to content</a>
      <aside className="fixed inset-y-0 left-0 hidden w-60 border-r border-line bg-subtle/60 lg:block"><Sidebar /></aside>
      {open && (
        <div className="fixed inset-0 z-50 bg-ink/30 lg:hidden" onClick={() => setOpen(false)}>
          <aside className="h-full w-64 border-r border-line bg-canvas" onClick={(e) => e.stopPropagation()}><Sidebar onNavigate={() => setOpen(false)} /></aside>
        </div>
      )}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-line bg-canvas/85 px-4 backdrop-blur lg:px-8">
          <div className="flex items-center gap-2">
            <button className="rounded-md p-1.5 text-body hover:bg-subtle lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">{open ? <X size={18} /> : <Menu size={18} />}</button>
            <span className="text-xs text-muted">Synthetic demo network · decision support only</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={clsx("mr-2 hidden items-center gap-1.5 text-xs sm:flex", live ? "text-success" : "text-muted")}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", live ? "bg-success" : "bg-faint")} /> {live ? "Live" : "Auto-refresh"}
            </span>
            <Link to="/alerts" className="relative rounded-md p-2 text-body hover:bg-subtle" aria-label={`${openAlerts} open alerts`}>
              <Bell size={16} />
              {openAlerts > 0 && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent" />}
            </Link>
            <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="rounded-md px-2 py-1.5 text-xs font-medium text-body hover:bg-subtle" aria-label="Toggle language">
              {lang === "en" ? "हिन्दी" : "EN"}
            </button>
            {loc.pathname !== "/copilot" && (
              <Link to="/copilot" className="ml-1 inline-flex h-8 items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 text-xs font-medium text-ink hover:bg-subtle"><Bot size={14} /> Ask copilot</Link>
            )}
          </div>
        </header>
        <main id="main" key={loc.pathname} className="mx-auto w-full max-w-[1280px] px-4 py-8 lg:px-8"><Outlet /></main>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Bot, ChevronRight, Droplet, FlaskConical, Menu, Phone, X } from "lucide-react";
import { api } from "../api/client";
import { useAuth } from "../lib/auth";
import { useI18n, type Key } from "../lib/i18n";
import { useLiveFeed } from "../lib/live";

type Item = { to: string; key: Key; roles?: string[] };
const PRIMARY: Item[] = [
  { to: "/", key: "command" }, { to: "/map", key: "map" }, { to: "/matrix", key: "matrix" }, { to: "/expiry", key: "expiry" },
  { to: "/forecast", key: "forecast" }, { to: "/transfers", key: "transfers" }, { to: "/alerts", key: "alerts" },
];
const UTILITY: Item[] = [
  { to: "/inventory", key: "inventory", roles: ["bank_manager", "hospital_user", "regional_coordinator", "admin"] },
  { to: "/donors", key: "donors", roles: ["bank_manager", "regional_coordinator", "admin"] },
  { to: "/register", key: "register", roles: ["bank_manager", "hospital_user", "admin"] },
  { to: "/evaluation", key: "eval" }, { to: "/quality", key: "quality" }, { to: "/articles", key: "articles" },
];

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="RaktSetu home">
      <Droplet size={30} className={light ? "text-white" : "text-brand-crimson"} fill="currentColor" aria-hidden />
      <span className={clsx("text-[1.7rem] font-extrabold leading-none tracking-[-0.06em]", light ? "text-white" : "text-black")}>RaktSetu</span>
      <span className={clsx("ml-1 border-l pl-2.5 text-lg leading-none", light ? "border-white/60 text-white" : "border-[#9a9a9a] text-brand-ink")}>Blood Network</span>
    </Link>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const { live, lastEvent } = useLiveFeed();
  const loc = useLocation();
  const [banner, setBanner] = useState(() => sessionStorage.getItem("raktsetu.banner") !== "closed");
  const [mobile, setMobile] = useState(false);
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api.get("/api/meta"), staleTime: 300_000 });
  const integ = meta.data?.integrations ?? {};
  const allowed = (i: Item) => !i.roles || i.roles.includes(user?.role ?? "");
  const isNet = user?.role === "regional_coordinator" || user?.role === "admin";

  return (
    <div className="flex min-h-screen flex-col bg-white text-brand-body">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[1001] focus:bg-white focus:p-2">Skip to main content</a>

      {banner && (
        <div className="bg-brand-plum text-white">
          <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-4 py-3 text-sm lg:px-8">
            <p><b>{t("synthetic")}.</b> {t("decision")}. Every number here comes from a reproducible synthetic network - see the Evaluation page.</p>
            <button onClick={() => { sessionStorage.setItem("raktsetu.banner", "closed"); setBanner(false); }} aria-label="Close notification"
              className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white text-brand-plum hover:bg-brand-pink"><X size={14} strokeWidth={3} /></button>
          </div>
        </div>
      )}

      <header className="sticky top-0 z-[999] bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-[1440px] px-4 lg:px-8">
          <div className="flex items-center justify-between gap-4 border-b border-[#ece7e7] py-4">
            <Logo />
            <div className="hidden items-center gap-5 text-[15px] font-semibold text-brand-ink xl:flex">
              {UTILITY.filter(allowed).map((i) => (
                <NavLink key={i.to} to={i.to} className={({ isActive }) => clsx("hover:text-brand-plum", isActive && "text-brand-plum underline decoration-2 underline-offset-8")}>{t(i.key)}</NavLink>
              ))}
              <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="hover:text-brand-plum" aria-label="Toggle language">{lang === "en" ? "हिन्दी" : "English"}</button>
              <Link to="/copilot" className="inline-flex items-center gap-1.5 rounded-full bg-brand-plum px-5 py-2.5 text-sm font-bold text-white hover:bg-brand-plum-dark"><Bot size={16} /> {t("copilot")}</Link>
              {isNet && <Link to="/stress" className="inline-flex items-center gap-1 rounded-full bg-brand-crimson px-5 py-2.5 text-sm font-bold text-white hover:bg-[#8f0c10]"><FlaskConical size={16} /> {t("stress")} <ChevronRight size={16} strokeWidth={3} /></Link>}
            </div>
            <button className="rounded-full p-2 text-brand-plum hover:bg-brand-pink xl:hidden" onClick={() => setMobile((m) => !m)} aria-label="Menu" aria-expanded={mobile}>
              {mobile ? <X /> : <Menu />}
            </button>
          </div>
          <nav aria-label="Main" className="hidden items-center justify-between py-4 xl:flex">
            <ul className="flex items-center gap-7">
              {PRIMARY.map((i) => (
                <li key={i.to}>
                  <NavLink to={i.to} end={i.to === "/"} className={({ isActive }) => clsx("text-[17px] font-semibold tracking-[-0.02em] text-brand-ink hover:text-brand-plum", isActive && "text-brand-plum underline decoration-[3px] underline-offset-[10px]")}>{t(i.key)}</NavLink>
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-4 text-sm">
              <span className={clsx("flex items-center gap-1.5", live ? "text-emerald-700" : "text-[#6b6b6b]")} title={lastEvent ?? ""}>
                <span className={clsx("h-2 w-2 rounded-full", live ? "animate-pulse bg-emerald-500" : "bg-[#9a9a9a]")} /> {live ? "Live" : "Auto-refresh"}
              </span>
              <span className="text-[#6b6b6b]">{user?.name} · <b className="text-brand-ink">{user?.role.replace("_", " ")}</b></span>
              <button onClick={logout} className="font-semibold text-brand-plum hover:underline">{t("logout")}</button>
            </div>
          </nav>
        </div>
        {mobile && (
          <nav aria-label="Mobile" className="border-t border-[#ece7e7] bg-white px-4 pb-4 xl:hidden" onClick={() => setMobile(false)}>
            <ul className="grid gap-1 py-2">
              {[...PRIMARY, ...UTILITY.filter(allowed), { to: "/copilot", key: "copilot" as Key }, ...(isNet ? [{ to: "/stress", key: "stress" as Key }] : [])].map((i) => (
                <li key={i.to}><NavLink to={i.to} end={i.to === "/"} className={({ isActive }) => clsx("block rounded-br-xl px-3 py-2 text-lg font-semibold", isActive ? "bg-brand-pink text-brand-plum" : "text-brand-ink")}>{t(i.key)}</NavLink></li>
              ))}
            </ul>
            <div className="flex items-center gap-4 text-sm">
              <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="font-semibold">{lang === "en" ? "हिन्दी" : "English"}</button>
              <button onClick={logout} className="font-semibold text-brand-plum">{t("logout")}</button>
            </div>
          </nav>
        )}
      </header>

      <main id="main" key={loc.pathname} className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-8 lg:px-8">
        <Outlet />
      </main>

      <footer className="mt-12 bg-brand-blush">
        <div className="bg-linear-to-r from-brand-magenta via-[#c4173c] to-[#e3202a] text-white">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-end justify-between gap-6 px-4 py-12 lg:px-8">
            <div>
              <p className="text-4xl font-bold leading-none tracking-[-0.045em]">Need blood urgently?</p>
              <p className="mt-1 font-serif text-4xl font-light">Find it <i>across</i> the network</p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link to="/matrix" className="inline-flex items-center gap-1 rounded-full bg-white px-6 py-3 font-bold text-brand-ink hover:bg-brand-pink">Search availability <ChevronRight size={18} strokeWidth={3} /></Link>
                <Link to="/donors" className="inline-flex items-center gap-1 rounded-full border border-white px-6 py-3 font-bold hover:bg-white/10">Draft a donor appeal <ChevronRight size={18} strokeWidth={3} /></Link>
              </div>
            </div>
            <p className="flex items-center gap-2 text-xl"><Phone size={20} /> In a medical emergency, call 112 / 108</p>
          </div>
        </div>
        <div className="mx-auto grid max-w-[1440px] gap-8 px-4 py-14 text-[15px] sm:grid-cols-2 lg:grid-cols-4 lg:px-8">
          <div>
            <Logo />
            <p className="mt-4 text-sm">A shared early-warning radar for blood across hospitals and blood banks. Decision support only - not a medical device. Humans approve every transfer.</p>
          </div>
          <div>
            <h3 className="mb-3 font-bold text-brand-ink">Network</h3>
            <ul className="space-y-2">{PRIMARY.slice(0, 4).map((i) => <li key={i.to}><Link to={i.to} className="hover:text-brand-plum">{t(i.key)}</Link></li>)}</ul>
          </div>
          <div>
            <h3 className="mb-3 font-bold text-brand-ink">Operations</h3>
            <ul className="space-y-2">{[...PRIMARY.slice(4), ...UTILITY.filter(allowed).slice(0, 2)].map((i) => <li key={i.to}><Link to={i.to} className="hover:text-brand-plum">{t(i.key)}</Link></li>)}</ul>
          </div>
          <div>
            <h3 className="mb-3 font-bold text-brand-ink">Google stack status</h3>
            <ul className="space-y-1 text-sm">
              {[["Gemini", integ.gemini?.enabled], ["Firebase Auth", integ.firebase_auth], ["Firestore live feed", integ.firestore_live_feed],
                ["Routes API", integ.routes_api], ["Calendar API", integ.google_calendar], ["BigQuery export", integ.bigquery_export], ["OR-Tools", integ.or_tools]].map(([k, v]) => (
                <li key={String(k)} className="flex justify-between gap-4"><span>{String(k)}</span><span className={v ? "font-semibold text-emerald-700" : "text-[#8a8a8a]"}>{v ? "on" : "fallback"}</span></li>
              ))}
            </ul>
          </div>
        </div>
        <div className="mx-auto max-w-[1440px] border-t border-[#e3dcdc] px-4 py-6 text-sm text-[#6b6b6b] lg:px-8">
          Synthetic demo data · Clinical rules must be confirmed against NACO / NBTC guidance · Built with Google Cloud, Firebase, Gemini and OR-Tools
        </div>
      </footer>
    </div>
  );
}

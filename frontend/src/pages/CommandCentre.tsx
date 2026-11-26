import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { api } from "../api/client";
import { AsOf, Card, Countdown, ErrorBox, Freshness, SectionTitle, SevBadge, Spinner, Stat } from "../components/ui";
import { COMP_LABEL, pct } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

const TILES = [
  { to: "/map", label: "Risk map", from: "#7a1a55", to2: "#b0306f" },
  { to: "/transfers", label: "Transfer desk", from: "#0b3fa8", to2: "#3b8fe0" },
  { to: "/expiry", label: "Use it or move it", from: "#9b1218", to2: "#d8343a" },
  { to: "/forecast", label: "Forecast explorer", from: "#353535", to2: "#5d5d5d" },
  { to: "/matrix", label: "Find blood nearby", from: "#681861", to2: "#8e3a87" },
  { to: "/alerts", label: "Alert centre", from: "#8a3b12", to2: "#c4672f" },
];

export default function CommandCentre() {
  const { t } = useI18n();
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: () => api.get("/api/kpis"), refetchInterval: POLL_MS });
  const alerts = useQuery({ queryKey: ["alerts", "top"], queryFn: () => api.get("/api/alerts?limit=6"), refetchInterval: POLL_MS });
  const regions = useQuery({ queryKey: ["regions"], queryFn: () => api.get("/api/regions") });
  if (kpis.isLoading) return <Spinner />;
  if (kpis.error) return <ErrorBox error={kpis.error} />;
  const k = kpis.data;
  const top = k.critical_countdowns[0];
  const rname = (id: string) => regions.data?.find((r: any) => String(r.id) === id)?.name ?? `Region ${id}`;
  return (
    <div className="-mt-8 space-y-12">
      {/* Hero */}
      <section className="relative -mx-4 overflow-hidden bg-linear-to-br from-brand-sky via-[#1556c4] to-brand-blue text-white lg:-mx-8">
        <div className="grid min-h-[440px] lg:grid-cols-2">
          <div className="flex flex-col justify-center px-6 py-12 lg:px-12">
            <h1 className="!text-white">
              <span className="block text-4xl font-bold leading-[1.02] tracking-[-0.05em] lg:text-[3.4rem]">Predict blood shortages</span>
              <span className="mt-1 block font-serif text-4xl font-light tracking-[-0.01em] lg:text-[3.2rem]">before they become emergencies</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg text-white/90">
              Probabilistic time-to-stockout across {k.facilities} hospitals and blood banks, turned into approved, constraint-checked transfers.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/transfers" className="inline-flex items-center gap-1 rounded-full bg-white px-6 py-3 font-bold text-brand-ink hover:bg-brand-pink">Review {k.pending_proposals} proposals <ChevronRight size={18} strokeWidth={3} /></Link>
              <Link to="/map" className="inline-flex items-center gap-1 rounded-full border border-white px-6 py-3 font-bold hover:bg-white/10">Open risk map <ChevronRight size={18} strokeWidth={3} /></Link>
            </div>
            <div className="mt-6"><AsOf iso={k.as_of} light /></div>
          </div>
          <div className="hero-angle relative hidden items-center justify-center bg-brand-pink p-10 lg:flex">
            {top ? (
              <Link to={`/forecast?f=${top.facility_id}&g=${encodeURIComponent(top.abo_rh)}&c=${top.component}`}
                className="w-full max-w-md rounded-br-[2.5rem] bg-white p-7 text-brand-ink shadow-xl ring-1 ring-black/5 hover:ring-brand-plum/40">
                <div className="flex items-center justify-between"><SevBadge sev="critical" label={t("critical")} /><span className="text-sm text-[#6b6b6b]">{top.facility_code}</span></div>
                <div className="mt-3 text-xl font-bold tracking-tight">{top.facility_name}</div>
                <div className="text-3xl font-bold text-brand-plum">{top.abo_rh} <span className="font-serif text-2xl font-light text-brand-ink">{COMP_LABEL[top.component]}</span></div>
                <div className="mt-4 text-xs font-semibold uppercase tracking-wider text-[#6b6b6b]">{t("tts")} (median)</div>
                <div className="text-5xl text-black"><Countdown hours={top.tts_p50} asOf={top.as_of} /></div>
                <div className="mt-3 text-sm">{pct(top.p_stockout_24)} {t("p24")} · {top.usable_units} {t("units")} · confidence {pct(top.confidence)}</div>
              </Link>
            ) : (
              <div className="text-center text-brand-ink"><div className="text-3xl font-bold tracking-tight">No critical series</div><div className="font-serif text-2xl font-light">the network is holding</div></div>
            )}
          </div>
        </div>
      </section>

      {/* KPIs */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <Stat label={t("critical")} value={k.severity_counts.critical} tone="critical" hint="likely to run out before resupply" />
        <Stat label={t("high")} value={k.severity_counts.high} tone="high" />
        <Stat label="Open alerts" value={k.open_alerts} hint="deduplicated, 6 h cooldown" />
        <Stat label="Pending proposals" value={k.pending_proposals} hint={<Link className="font-semibold text-brand-plum underline" to="/transfers">review</Link>} />
        <Stat label="Wastage avoided" value={`${k.wastage_avoided_units} u`} tone="low" hint="near-expiry units rescued" />
        <Stat label="Network resilience" value={k.resilience_score != null ? `${k.resilience_score}%` : "-"} hint="RBC series with >= 2 days cover" />
      </section>

      {/* Countdowns */}
      {k.critical_countdowns.length > 1 && (
        <section>
          <SectionTitle title="Critical countdowns" accent={<>median time <i>to</i> stockout</>} />
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {k.critical_countdowns.map((c: any) => (
              <Link key={`${c.facility_id}${c.abo_rh}${c.component}`} to={`/forecast?f=${c.facility_id}&g=${encodeURIComponent(c.abo_rh)}&c=${c.component}`}
                className="rounded-br-[2rem] bg-brand-panel p-5 hover:bg-brand-pink">
                <div className="flex items-center justify-between"><SevBadge sev="critical" label={t("critical")} /><span className="text-xs">{c.facility_code}</span></div>
                <div className="mt-2 font-bold text-brand-ink">{c.facility_name}</div>
                <div className="text-2xl font-bold text-brand-plum">{c.abo_rh} <span className="text-base font-semibold text-brand-ink">{COMP_LABEL[c.component]}</span></div>
                <div className="mt-1 text-3xl text-black"><Countdown hours={c.tts_p50} asOf={c.as_of} /></div>
                <div className="mt-1 text-xs">{pct(c.p_stockout_24)} {t("p24")} · {c.usable_units} {t("units")}</div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Quick-link tiles */}
      <section className="-mx-4 bg-brand-pink px-4 py-12 lg:-mx-8 lg:px-8">
        <SectionTitle title="Act on the network" accent={<><i>from</i> one place</>} />
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TILES.map((tile) => (
            <Link key={tile.to} to={tile.to} className="group relative flex h-36 items-end overflow-hidden rounded-tr-[2.5rem] p-6 text-white"
              style={{ background: `linear-gradient(135deg, ${tile.from}, ${tile.to2})` }}>
              <span className="absolute -right-6 -top-8 h-32 w-32 rounded-full bg-white/10 transition-transform group-hover:scale-125" aria-hidden />
              <span className="flex items-center gap-1 text-2xl font-bold tracking-tight">{tile.label} <ChevronRight size={22} strokeWidth={3} /></span>
            </Link>
          ))}
        </div>
      </section>

      {/* Resilience + alerts */}
      <section className="grid gap-6 lg:grid-cols-3">
        <Card title="Regional resilience" tone="grey" className="lg:col-span-1">
          <ul className="space-y-3">
            {Object.entries(k.regional_resilience ?? {}).map(([rid, v]) => (
              <li key={rid}>
                <div className="flex justify-between text-sm"><span className="font-semibold text-brand-ink">{rname(rid)}</span><span className="font-bold">{String(v)}%</span></div>
                <div className="mt-1 h-2 rounded-full bg-white"><div className="h-2 rounded-full bg-brand-plum" style={{ width: `${v}%` }} /></div>
              </li>
            ))}
          </ul>
          {k.stale_facilities.length > 0 && (
            <div className="mt-5 border-t border-[#ddd] pt-4">
              <div className="mb-2 text-xs font-bold uppercase tracking-wider text-[#6b6b6b]">Facilities not reporting</div>
              {k.stale_facilities.map((f: any) => <div key={f.id} className="flex justify-between text-sm"><span>{f.name}</span><Freshness hours={f.hours} /></div>)}
            </div>
          )}
        </Card>
        <Card title="Latest alerts" action={<Link to="/alerts" className="inline-flex items-center text-sm font-bold text-brand-plum">All alerts <ChevronRight size={16} strokeWidth={3} /></Link>} className="lg:col-span-2">
          <ul className="divide-y divide-[#eee]">
            {(alerts.data ?? []).map((a: any) => (
              <li key={a.id} className="flex items-start gap-3 py-3 text-[15px]"><SevBadge sev={a.severity} /><span>{a.message}</span></li>
            ))}
            {alerts.data?.length === 0 && <li className="py-2 text-sm">No open alerts.</li>}
          </ul>
        </Card>
      </section>
    </div>
  );
}

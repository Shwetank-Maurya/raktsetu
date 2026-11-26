import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { AsOf, Card, Countdown, ErrorBox, Freshness, SevBadge, Spinner, Stat } from "../components/ui";
import { COMP_LABEL, pct } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

export default function CommandCentre() {
  const { t } = useI18n();
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: () => api.get("/api/kpis"), refetchInterval: POLL_MS });
  const alerts = useQuery({ queryKey: ["alerts", "top"], queryFn: () => api.get("/api/alerts?limit=6"), refetchInterval: POLL_MS });
  const regions = useQuery({ queryKey: ["regions"], queryFn: () => api.get("/api/regions") });
  if (kpis.isLoading) return <Spinner />;
  if (kpis.error) return <ErrorBox error={kpis.error} />;
  const k = kpis.data;
  const rname = (id: string) => regions.data?.find((r: any) => String(r.id) === id)?.name ?? `Region ${id}`;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold">{t("command")}</h1>
          <p className="text-sm text-slate-500">Probabilistic time-to-stockout across {k.facilities} facilities. <AsOf iso={k.as_of} /></p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label={t("critical")} value={k.severity_counts.critical} tone="critical" hint="series likely to run out before resupply" />
        <Stat label={t("high")} value={k.severity_counts.high} tone="high" />
        <Stat label="Open alerts" value={k.open_alerts} hint="deduplicated, 6 h cooldown" />
        <Stat label="Pending proposals" value={k.pending_proposals} hint={<Link className="text-rose-700 underline" to="/transfers">review</Link>} />
        <Stat label="Wastage avoided" value={`${k.wastage_avoided_units} u`} tone="low" hint="near-expiry units rescued by approved moves" />
        <Stat label="Network resilience" value={k.resilience_score != null ? `${k.resilience_score}%` : "-"} hint="RBC series with >= 2 days cover and not high risk" />
      </div>
      <Card title="Critical countdowns - median time to stockout">
        {k.critical_countdowns.length === 0 ? <p className="text-sm text-slate-500">No critical series right now.</p> : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {k.critical_countdowns.map((c: any) => (
              <Link key={`${c.facility_id}${c.abo_rh}${c.component}`} to={`/forecast?f=${c.facility_id}&g=${encodeURIComponent(c.abo_rh)}&c=${c.component}`}
                className="rounded-xl border-2 border-[#D55E00] bg-orange-50 p-3 hover:bg-orange-100">
                <div className="flex items-center justify-between"><SevBadge sev="critical" label={t("critical")} /><span className="text-xs text-slate-500">{c.facility_code}</span></div>
                <div className="mt-1 font-semibold">{c.facility_name}</div>
                <div className="text-2xl font-bold text-[#B34700]">{c.abo_rh} <span className="text-base font-medium">{COMP_LABEL[c.component]}</span></div>
                <div className="mt-1 text-3xl text-slate-900"><Countdown hours={c.tts_p50} asOf={c.as_of} /></div>
                <div className="mt-1 text-xs text-slate-600">{pct(c.p_stockout_24)} {t("p24")} · {c.usable_units} {t("units")} · confidence {pct(c.confidence)}</div>
              </Link>
            ))}
          </div>
        )}
      </Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Regional resilience" className="lg:col-span-1">
          <ul className="space-y-2">
            {Object.entries(k.regional_resilience ?? {}).map(([rid, v]) => (
              <li key={rid}>
                <div className="flex justify-between text-sm"><span>{rname(rid)}</span><span className="font-semibold">{String(v)}%</span></div>
                <div className="h-2 rounded bg-slate-100"><div className="h-2 rounded bg-[#009E73]" style={{ width: `${v}%` }} /></div>
              </li>
            ))}
          </ul>
          {k.stale_facilities.length > 0 && (
            <div className="mt-4">
              <div className="mb-1 text-xs font-semibold text-slate-600">Facilities not reporting</div>
              {k.stale_facilities.map((f: any) => <div key={f.id} className="flex justify-between text-sm"><span>{f.name}</span><Freshness hours={f.hours} /></div>)}
            </div>
          )}
        </Card>
        <Card title="Latest alerts" action={<Link to="/alerts" className="text-xs text-rose-700 underline">all alerts</Link>} className="lg:col-span-2">
          <ul className="divide-y divide-slate-100">
            {(alerts.data ?? []).map((a: any) => (
              <li key={a.id} className="flex items-start gap-2 py-2 text-sm"><SevBadge sev={a.severity} /><span>{a.message}</span></li>
            ))}
            {alerts.data?.length === 0 && <li className="py-2 text-sm text-slate-500">No open alerts.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}

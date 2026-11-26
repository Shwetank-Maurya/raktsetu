import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, Bell, Droplet, Truck } from "lucide-react";
import { api } from "../api/client";
import { AsOf, Bar, Card, Countdown, EmptyState, ErrorBox, PageHeader, SevBadge, Skeleton, SOFT, Stat } from "../components/ui";
import { COMP_LABEL, hrs, pct } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

const SEV_ORDER = ["critical", "high", "medium", "low"] as const;

export default function CommandCentre() {
  const { t } = useI18n();
  const nav = useNavigate();
  const kpis = useQuery({ queryKey: ["kpis"], queryFn: () => api.get("/api/kpis"), refetchInterval: POLL_MS });
  const risk = useQuery({ queryKey: ["risk", "top"], queryFn: () => api.get("/api/risk?limit=8"), refetchInterval: POLL_MS });
  const alerts = useQuery({ queryKey: ["alerts", "top"], queryFn: () => api.get("/api/alerts?limit=5"), refetchInterval: POLL_MS });

  if (kpis.error) return <ErrorBox error={kpis.error} />;
  const k = kpis.data;
  const total = k ? SEV_ORDER.reduce((a, s) => a + (k.severity_counts[s] ?? 0), 0) : 0;
  const top = k?.critical_countdowns?.[0];
  const go = (r: any) => nav(`/forecast?f=${r.facility_id}&g=${encodeURIComponent(r.abo_rh)}&c=${r.component}`);

  return (
    <div className="space-y-6">
      <PageHeader title={t("command")} description={k ? <>Network-wide stockout risk across {k.facilities} facilities. <AsOf iso={k.as_of} /></> : "Loading network…"} />

      {top && (
        <Link to={`/forecast?f=${top.facility_id}&g=${encodeURIComponent(top.abo_rh)}&c=${top.component}`}
          className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#f3d2c2] bg-[#fdf6f2] px-5 py-4 hover:border-[#e9b79f]">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-[#D55E00]" />
            <div>
              <div className="text-sm font-medium text-ink">{top.facility_name} · {top.abo_rh} {COMP_LABEL[top.component]}</div>
              <div className="text-xs text-muted">{pct(top.p_stockout_24)} chance of stockout in 24 h · {top.usable_units} usable units · confidence {pct(top.confidence)}</div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wider text-muted">Median time to stockout</div>
            <div className="text-2xl font-semibold text-[#a34000]"><Countdown hours={top.tts_p50} asOf={top.as_of} /></div>
          </div>
        </Link>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {k ? (
          <>
            <Stat label="Critical series" value={k.severity_counts.critical ?? 0} tone="critical" icon={AlertTriangle} hint="Likely to run out before resupply" />
            <Stat label="High risk" value={k.severity_counts.high ?? 0} tone="high" icon={Droplet} hint="Real risk within 48 h" />
            <Stat label="Pending transfers" value={k.pending_proposals} icon={Truck} hint={<Link to="/transfers" className="text-accent hover:underline">Review proposals</Link>} />
            <Stat label="Open alerts" value={k.open_alerts} icon={Bell} hint={`${k.wastage_avoided_units} units rescued from expiry`} />
          </>
        ) : [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[104px]" />)}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="At risk now" description="Highest-risk series, ordered by severity" padded={false} className="lg:col-span-2"
          action={<Link to="/map" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">Risk map <ArrowRight size={12} /></Link>}>
          {risk.isLoading ? <div className="space-y-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line"><th className="px-5 py-2.5">Facility</th><th>Series</th><th className="w-40">Stockout in 24 h</th><th>Time to stockout</th><th className="pr-5 text-right">Units</th></tr></thead>
                <tbody>
                  {(risk.data?.items ?? []).map((r: any) => (
                    <tr key={`${r.facility_id}${r.abo_rh}${r.component}`} tabIndex={0} role="link" onClick={() => go(r)} onKeyDown={(e) => e.key === "Enter" && go(r)}
                      className="cursor-pointer border-b border-line-soft last:border-0 hover:bg-canvas">
                      <td className="px-5 py-2.5"><div className="font-medium text-ink">{r.facility_name}</div><div className="text-xs text-muted">{r.facility_code}</div></td>
                      <td><div className="flex items-center gap-2"><span className="font-medium text-ink">{r.abo_rh}</span><span className="text-muted">{COMP_LABEL[r.component]}</span></div><SevBadge sev={r.severity} /></td>
                      <td><div className="flex items-center gap-2 pr-4"><Bar value={r.p_stockout_24} color={SOFT[r.severity as keyof typeof SOFT]?.dot} /><span className="w-9 text-right text-xs">{pct(r.p_stockout_24)}</span></div></td>
                      <td className="text-ink">{hrs(r.tts_p50)}</td>
                      <td className="pr-5 text-right text-ink">{r.usable_units}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <Card title="Risk distribution" description={k ? `${total} series monitored` : undefined}>
            {k ? (
              <ul className="space-y-3">
                {SEV_ORDER.map((s) => {
                  const v = k.severity_counts[s] ?? 0;
                  return (
                    <li key={s}>
                      <div className="mb-1 flex justify-between text-xs"><SevBadge sev={s} label={t(s)} /><span className="text-ink">{v}</span></div>
                      <Bar value={total ? v / total : 0} color={SOFT[s].dot} />
                    </li>
                  );
                })}
              </ul>
            ) : <Skeleton className="h-28" />}
          </Card>

          <Card title="Latest alerts" padded={false} action={<Link to="/alerts" className="text-xs font-medium text-accent hover:underline">All</Link>}>
            {(alerts.data ?? []).length === 0 && !alerts.isLoading ? <div className="p-5"><EmptyState title="No open alerts" /></div> : (
              <ul>
                {(alerts.data ?? []).map((a: any) => (
                  <li key={a.id} className="border-b border-line-soft px-5 py-3 last:border-0">
                    <SevBadge sev={a.severity} />
                    <p className="mt-1 line-clamp-2 text-xs text-body">{a.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

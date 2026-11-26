import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { AsOf, Card, ErrorBox, Spinner, Stat } from "../components/ui";
import { COMP_LABEL } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

export default function Expiry() {
  const { t } = useI18n();
  const [hours, setHours] = useState(96);
  const q = useQuery({ queryKey: ["expiring", hours], queryFn: () => api.get(`/api/inventory/expiring?hours=${hours}`), refetchInterval: POLL_MS });
  const k = useQuery({ queryKey: ["kpis"], queryFn: () => api.get("/api/kpis") });
  const rescue = useQuery({ queryKey: ["transfers", "rescue"], queryFn: () => api.get("/api/transfers?status=proposed&limit=200") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  const buckets = Object.entries(q.data.buckets).map(([name, v]) => ({ name, units: v as number }));
  const moves = (rescue.data ?? []).filter((t: any) => (t.reason?.saves?.wastage_units ?? 0) > 0);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div><h1>{t("expiry")}</h1><p className="text-sm text-muted">First-Expiry-First-Out. Use it or move it. <AsOf iso={q.data.as_of} /></p></div>
        <label className="text-sm">Window&nbsp;
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))} className="rounded border border-line px-2 py-1">
            {[24, 48, 72, 96, 168].map((h) => <option key={h} value={h}>{h} h</option>)}
          </select>
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Wastage avoided" value={`${k.data?.wastage_avoided_units ?? 0} units`} tone="low" hint="rescue transfers approved so far" />
        <Stat label="Projected to expire unused (7 d)" value={`${k.data?.expected_wastage_units ?? "-"} units`} tone="high" hint="Monte Carlo expected wastage, all series" />
        <Stat label="Rescue moves proposed" value={moves.length} hint={<Link to="/transfers" className="text-accent underline">open Transfer Desk</Link>} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Units by remaining life">
          <div className="h-56">
            <ResponsiveContainer><BarChart data={buckets}><XAxis dataKey="name" fontSize={12} /><YAxis fontSize={12} allowDecimals={false} /><Tooltip /><Bar dataKey="units" fill="#E69F00" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer>
          </div>
        </Card>
        <Card title="Use-it-or-move-it recommendations" className="lg:col-span-2">
          {moves.length === 0 ? <p className="text-sm text-muted">No rescue moves proposed right now.</p> : (
            <ul className="divide-y divide-line-soft text-sm">
              {moves.slice(0, 10).map((m: any) => (
                <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <span>Move <b>{m.quantity} x {m.abo_rh} {COMP_LABEL[m.component]}</b> from {m.from_name} to {m.to_name}</span>
                  <span className="text-xs text-body">saves {m.reason.saves.wastage_units} from expiry · arrives with {Math.round(m.min_life_on_arrival_h)} h life · ETA {Math.round(m.eta_minutes)} min</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card title={`Expiring within ${hours} h (FEFO order)`}>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-muted"><th>Facility</th><th>Group</th><th>Component</th><th>Units</th><th>Earliest expiry</th></tr></thead>
          <tbody>{q.data.groups.slice(0, 60).map((g: any) => (
            <tr key={`${g.facility_id}${g.abo_rh}${g.component}`} className="border-t border-line-soft">
              <td>{g.facility_name}</td><td className="font-semibold">{g.abo_rh}</td><td>{COMP_LABEL[g.component]}</td><td>{g.units}</td>
              <td className={g.earliest_expiry_h < 24 ? "font-semibold text-[#a34000]" : ""}>{g.earliest_expiry_h} h</td>
            </tr>))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

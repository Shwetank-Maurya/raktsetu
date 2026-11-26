import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card, ErrorBox, Freshness, Spinner } from "../components/ui";
import { ist } from "../lib/format";
import { useI18n } from "../lib/i18n";

export default function DataQuality() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["dq"], queryFn: () => api.get("/api/data-quality") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  return (
    <div className="space-y-4">
      <div><h1 className="text-xl font-bold">{t("quality")}</h1>
        <p className="text-sm text-slate-500">Messy reality, handled: silent facilities, late rows, event days and entries that validation rejected.</p></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Facility reporting (last 30 days)">
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-slate-500"><th>Facility</th><th>Fresh</th><th>Days reported</th><th>Late rows</th><th>Event days</th></tr></thead>
            <tbody>{q.data.facilities.map((f: any) => (
              <tr key={f.id} className="border-t border-slate-100"><td>{f.code} {f.name}</td><td><Freshness hours={f.freshness_h} /></td>
                <td className={f.reported_days_30 < 28 ? "font-semibold text-[#B34700]" : ""}>{f.reported_days_30}</td><td>{f.late_rows_30}</td><td>{f.event_days_30}</td></tr>))}
            </tbody></table>
        </Card>
        <div className="space-y-4">
          <Card title="Rejected entries (422 with reason, kept for review)">
            <ul className="space-y-2 text-sm">{q.data.rejected_entries.map((r: any) => (
              <li key={r.id} className="rounded border border-red-100 bg-red-50 p-2"><div className="font-medium text-red-900">{r.reason}</div>
                <code className="text-[11px] text-slate-600">{JSON.stringify(r.payload)}</code></li>))}
              {q.data.rejected_entries.length === 0 && <li className="text-slate-500">None.</li>}
            </ul>
          </Card>
          {q.data.recent_audit.length > 0 && (
            <Card title="Audit log (every human decision)">
              <ul className="space-y-1 text-xs">{q.data.recent_audit.map((a: any, i: number) => (
                <li key={i} className="flex justify-between gap-2"><span><b>{a.action}</b> {a.entity} {a.entity_id}</span><span className="text-slate-500">{a.actor} · {ist(a.ts)}</span></li>))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { endpoints } from "../api/endpoints";

import { AsOf, Card, ErrorBox, Freshness, Select, Spinner, Tabs } from "../components/ui";
import { COMP_LABEL, COMPONENTS, GROUPS } from "../lib/format";
import { useAuth } from "../lib/auth-context";
import { useI18n } from "../lib/i18n-context";
import { POLL_MS } from "../lib/live";

function cellTone(n: number) {
  if (n === 0) return "bg-[#fdeee6] text-[#a34000] font-semibold";
  if (n <= 2) return "bg-[#fdf4e3] text-[#8a5800] font-medium";
  if (n <= 5) return "bg-[#fbf8dc] text-[#6f6400]";
  return "text-body";
}

export default function Matrix() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [comp, setComp] = useState("RBC");
  const [sg, setSg] = useState("O-");
  const [sc, setSc] = useState("RBC");
  const [searched, setSearched] = useState(false);
  const m = useQuery({ queryKey: ["matrix"], queryFn: endpoints.matrix, refetchInterval: POLL_MS });
  const search = useQuery({
    queryKey: ["search", sg, sc], enabled: searched,
    queryFn: () => endpoints.availability({ abo_rh: sg, component: sc, radius_km: 50, facility_id: user?.facility_id }),
  });
  if (m.error) return <ErrorBox error={m.error} />;
  if (!m.data) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div><h1>{t("matrix")}</h1><AsOf iso={m.data.as_of} /></div>
        <Tabs value={comp} onChange={setComp} options={COMPONENTS.map((c) => [c, COMP_LABEL[c]] as [string, string])} />
      </div>
      <Card title={`Usable ${COMP_LABEL[comp]} units (excludes reserved, quarantined, in-transit and below minimum remaining life)`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-muted"><th className="py-1 pr-2">Facility</th><th>Fresh</th>{GROUPS.map((g) => <th key={g} className="px-1 text-center">{g}</th>)}<th className="text-right">Total</th></tr></thead>
            <tbody>
              {m.data.facilities.map((f) => {
                const vals = GROUPS.map((g) => f.cells[`${g}|${comp}`]?.usable ?? 0);
                return (
                  <tr key={f.facility_id} className="border-t border-line-soft">
                    <td className="py-1 pr-2"><div className="font-medium">{f.name}</div><div className="text-xs text-muted">{f.code} · {f.type.replace("_", " ")}</div></td>
                    <td><Freshness hours={f.freshness_h} /></td>
                    {vals.map((v, i) => {
                      const c = f.cells[`${GROUPS[i]}|${comp}`];
                      return <td key={i} className="px-0.5 py-0.5 text-center"><span title={c ? `reserved ${c.reserved ?? 0}, quarantined ${c.quarantined ?? 0}, in transit ${c.in_transit ?? 0}` : "none"} className={`inline-block w-10 rounded py-0.5 font-mono text-xs ${cellTone(v)}`}>{v}</span></td>;
                    })}
                    <td className="text-right font-semibold">{vals.reduce((a, b) => a + b, 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">Tint marks low stock: 0 units, 1–2, 3–5. The number is always printed.</p>
      </Card>
      <Card title="Intelligent availability search (compatibility-aware, ranked by exact match, ETA and shelf life)">
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Blood group" value={sg} onChange={setSg} options={[...GROUPS]} />
          <Select label="Component" value={sc} onChange={setSc} options={COMPONENTS.map((c) => [c, COMP_LABEL[c]] as [string, string])} />
          <button onClick={() => { setSearched(true); search.refetch(); }} className="rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-white hover:bg-accent-strong">Find within 50 km</button>
        </div>
        {search.data && (
          <table className="mt-3 w-full text-sm">
            <thead><tr className="text-left text-xs text-muted"><th>Facility</th><th>Group</th><th>Units</th><th>ETA</th><th>Earliest expiry</th><th>Note</th></tr></thead>
            <tbody>{search.data.results.map((r) => (
              <tr key={r.facility_id + r.abo_rh} className="border-t border-line-soft">
                <td>{r.facility_name}</td><td className="font-semibold">{r.abo_rh}</td><td>{r.units}</td><td>{r.eta_minutes} min</td><td>{Math.round(r.earliest_expiry_h)} h</td>
                <td>{r.needs_clinician_approval ? <span className="rounded bg-amber-100 px-1 text-xs text-amber-900">compatible substitute - clinician approval</span> : <span className="text-xs text-emerald-700">exact match</span>}</td>
              </tr>))}
              {search.data.results.length === 0 && <tr><td colSpan={6} className="py-2 text-muted">Nothing usable within range. Consider a donor appeal.</td></tr>}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

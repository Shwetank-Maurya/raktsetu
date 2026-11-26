import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, enc } from "../api/client";
import { AsOf, Card, ErrorBox, Freshness, Select, Spinner } from "../components/ui";
import { COMP_LABEL, COMPONENTS, GROUPS } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

function cellTone(n: number) {
  if (n === 0) return "bg-[#D55E00] text-white";
  if (n <= 2) return "bg-[#E69F00]/80 text-black";
  if (n <= 5) return "bg-[#F0E442]/70 text-black";
  return "bg-emerald-50 text-emerald-900";
}

export default function Matrix() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [comp, setComp] = useState("RBC");
  const [sg, setSg] = useState("O-");
  const [sc, setSc] = useState("RBC");
  const [searched, setSearched] = useState(false);
  const m = useQuery({ queryKey: ["matrix"], queryFn: () => api.get("/api/inventory/matrix"), refetchInterval: POLL_MS });
  const search = useQuery({
    queryKey: ["search", sg, sc], enabled: searched,
    queryFn: () => api.get(`/api/availability/search?abo_rh=${enc(sg)}&component=${sc}&radius_km=50${user?.facility_id ? `&facility_id=${user.facility_id}` : ""}`),
  });
  if (m.isLoading) return <Spinner />;
  if (m.error) return <ErrorBox error={m.error} />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div><h1>{t("matrix")}<span className="accent">every group, every facility</span></h1><AsOf iso={m.data.as_of} /></div>
        <div className="flex gap-1" role="tablist">
          {COMPONENTS.map((c) => (
            <button key={c} role="tab" aria-selected={comp === c} onClick={() => setComp(c)} className={`rounded-full px-4 py-1.5 text-sm font-semibold ${comp === c ? "bg-brand-plum text-white" : "bg-white text-brand-ink ring-1 ring-[#cfc6c6]"}`}>{COMP_LABEL[c]}</button>
          ))}
        </div>
      </div>
      <Card title={`Usable ${COMP_LABEL[comp]} units (excludes reserved, quarantined, in-transit and below minimum remaining life)`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-[#6b6b6b]"><th className="py-1 pr-2">Facility</th><th>Fresh</th>{GROUPS.map((g) => <th key={g} className="px-1 text-center">{g}</th>)}<th className="text-right">Total</th></tr></thead>
            <tbody>
              {m.data.facilities.map((f: any) => {
                const vals = GROUPS.map((g) => f.cells[`${g}|${comp}`]?.usable ?? 0);
                return (
                  <tr key={f.facility_id} className="border-t border-slate-100">
                    <td className="py-1 pr-2"><div className="font-medium">{f.name}</div><div className="text-xs text-[#6b6b6b]">{f.code} · {f.type.replace("_", " ")}</div></td>
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
        <p className="mt-2 text-xs text-[#6b6b6b]">Colour-blind-safe scale with the number always printed: 0 = vermillion, 1-2 = orange, 3-5 = yellow, 6+ = green.</p>
      </Card>
      <Card title="Intelligent availability search (compatibility-aware, ranked by exact match, ETA and shelf life)">
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Blood group" value={sg} onChange={setSg} options={[...GROUPS]} />
          <Select label="Component" value={sc} onChange={setSc} options={COMPONENTS.map((c) => [c, COMP_LABEL[c]] as [string, string])} />
          <button onClick={() => { setSearched(true); search.refetch(); }} className="rounded-full bg-brand-plum px-5 py-2 text-sm font-bold text-white hover:bg-brand-plum-dark">Find within 50 km</button>
        </div>
        {search.data && (
          <table className="mt-3 w-full text-sm">
            <thead><tr className="text-left text-xs text-[#6b6b6b]"><th>Facility</th><th>Group</th><th>Units</th><th>ETA</th><th>Earliest expiry</th><th>Note</th></tr></thead>
            <tbody>{search.data.results.map((r: any) => (
              <tr key={r.facility_id + r.abo_rh} className="border-t border-slate-100">
                <td>{r.facility_name}</td><td className="font-semibold">{r.abo_rh}</td><td>{r.units}</td><td>{r.eta_minutes} min</td><td>{Math.round(r.earliest_expiry_h)} h</td>
                <td>{r.needs_clinician_approval ? <span className="rounded bg-amber-100 px-1 text-xs text-amber-900">compatible substitute - clinician approval</span> : <span className="text-xs text-emerald-700">exact match</span>}</td>
              </tr>))}
              {search.data.results.length === 0 && <tr><td colSpan={6} className="py-2 text-[#6b6b6b]">Nothing usable within range. Consider a donor appeal.</td></tr>}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

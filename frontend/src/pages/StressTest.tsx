import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import MapView from "../components/MapView";
import { Button, Card, ErrorBox, SevBadge, Spinner, Stat } from "../components/ui";
import { COMP_LABEL, SEV, hrs, pct, type Sev } from "../lib/format";
import { track } from "../lib/firebase";
import { useI18n } from "../lib/i18n";

export default function StressTest() {
  const { t } = useI18n();
  const [pick, setPick] = useState<[number, number] | null>([28.6304, 77.2177]);
  const [casualties, setCasualties] = useState(40);
  const [hours, setHours] = useState(12);
  const [crit, setCrit] = useState(20);
  const geo = useQuery({ queryKey: ["map", "risk"], queryFn: () => api.get("/api/map/risk") });
  const assumptions = useQuery({ queryKey: ["assumptions"], queryFn: () => api.get("/api/simulate/assumptions") });
  const sim = useMutation({
    mutationFn: () => api.read("/api/simulate/incident", {
      lat: pick![0], lng: pick![1], casualties, hours, radius_km: 25,
      severity_mix: { critical: crit / 100, serious: Math.max(0, (100 - crit) * 0.4) / 100, minor: Math.max(0, (100 - crit) * 0.6) / 100 },
    }),
    onSuccess: () => track("stress_test", { casualties }),
  });
  const r = sim.data;
  const broken = new Map<number, string>();
  r?.affected.forEach((a: any) => { if (!broken.has(a.facility_id) || a.after === "critical") broken.set(a.facility_id, a.after); });
  const markers = (geo.data?.features ?? []).map((f: any) => {
    const p = f.properties;
    const sev = (broken.get(p.id) ?? (r ? "low" : p.severity)) as Sev;
    return { id: p.id, lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], color: SEV[sev].color, size: broken.has(p.id) ? 26 : 14, label: `${p.name}: ${sev}` };
  });
  const routes = (r?.plan ?? []).map((p: any) => ({ from: [p.from_lat, p.from_lng] as [number, number], to: [p.to_lat, p.to_lng] as [number, number], color: "#0072B2", label: `${p.quantity} x ${p.abo_rh} ${p.component}` }));
  return (
    <div className="space-y-4">
      <div><h1>{t("stress")}: mass-casualty what-if<span className="accent"><i>what if</i> it happened today?</span></h1>
        <p className="text-sm text-[#6b6b6b]">Click the map to place an incident. RaktSetu adds the casualty demand to the receiving hospitals, re-runs the Monte Carlo risk engine and the optimizer, and shows which facilities break and the response plan. Nothing is saved.</p></div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2"><MapView markers={markers} routes={routes} showHeat={false} pick={pick} onMapClick={(la, ln) => setPick([la, ln])} height={520} /></div>
        <Card title="Incident">
          <div className="space-y-3 text-sm">
            <div className="text-xs text-[#6b6b6b]">Location: {pick ? `${pick[0].toFixed(4)}, ${pick[1].toFixed(4)}` : "click the map"}</div>
            <label className="block">Casualties: <b>{casualties}</b><input type="range" min={5} max={300} value={casualties} onChange={(e) => setCasualties(+e.target.value)} className="w-full" /></label>
            <label className="block">Critical share: <b>{crit}%</b><input type="range" min={5} max={60} value={crit} onChange={(e) => setCrit(+e.target.value)} className="w-full" /></label>
            <label className="block">Within: <b>{hours} h</b><input type="range" min={1} max={48} value={hours} onChange={(e) => setHours(+e.target.value)} className="w-full" /></label>
            <Button onClick={() => sim.mutate()} disabled={!pick || sim.isPending} className="w-full">{sim.isPending ? "Simulating 500 paths per series..." : "Run stress test"}</Button>
            <ErrorBox error={sim.error} />
            {assumptions.data && (
              <details className="text-xs text-brand-body"><summary className="cursor-pointer">Assumptions (editable via API, audited)</summary>
                <pre className="mt-1 max-h-48 overflow-auto rounded bg-brand-blush p-2">{JSON.stringify(assumptions.data.units_per_casualty, null, 1)}</pre>
                <div>{assumptions.data.note}</div>
              </details>
            )}
          </div>
        </Card>
      </div>
      {sim.isPending && <Spinner label="Re-running risk for every series" />}
      {r && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Facilities breaking" value={r.facilities_breaking} tone="critical" />
            {Object.entries(r.total_extra_units).map(([c, v]) => <Stat key={c} label={`Extra ${COMP_LABEL[c]}`} value={`${v} u`} />)}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Which series break">
              <table className="w-full text-sm"><thead><tr className="text-left text-xs text-[#6b6b6b]"><th>Facility</th><th>Series</th><th>Before → after</th><th>P24</th><th>TTS</th></tr></thead>
                <tbody>{r.affected.slice(0, 15).map((a: any, i: number) => (
                  <tr key={i} className="border-t border-slate-100"><td>{a.name}</td><td>{a.abo_rh} {a.component}</td><td><SevBadge sev={a.before} /> → <SevBadge sev={a.after} /></td><td>{pct(a.p_stockout_24)}</td><td>{hrs(a.tts_p50)}</td></tr>))}
                </tbody></table>
            </Card>
            <Card title={`Response plan (${r.plan.length} transfers, ${r.unmet.length} unmet needs)`}>
              <ul className="space-y-1 text-sm">{r.plan.slice(0, 15).map((p: any, i: number) => (
                <li key={i}><b>{p.quantity} x {p.abo_rh} {p.component}</b>: {p.from_name} → {p.to_name} <span className="text-xs text-[#6b6b6b]">({Math.round(p.eta_minutes)} min{p.needs_clinician_approval ? ", substitute" : ""})</span></li>))}
              </ul>
              {r.unmet.length > 0 && <p className="mt-2 text-xs text-[#B34700]">Unmet after all feasible transfers: trigger donor appeals for {[...new Set(r.unmet.map((u: any) => u.abo_rh))].join(", ")}.</p>}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

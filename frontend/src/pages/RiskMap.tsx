import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import MapView, { mapsProvider } from "../components/MapView";
import { Card, ErrorBox, Freshness, SevBadge, Spinner } from "../components/ui";
import { COMP_LABEL, COMPONENTS, GROUPS, SEV, hrs, pct, type Sev } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

export default function RiskMap() {
  const { t } = useI18n();
  const [heat, setHeat] = useState(true);
  const [routes, setRoutes] = useState(true);
  const [comp, setComp] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const geo = useQuery({ queryKey: ["map", "risk"], queryFn: () => api.get("/api/map/risk"), refetchInterval: POLL_MS });
  const heatQ = useQuery({ queryKey: ["map", "heat", comp], queryFn: () => api.get(`/api/map/heat${comp ? `?component=${comp}` : ""}`) });
  const tr = useQuery({ queryKey: ["transfers", "map"], queryFn: () => api.get("/api/transfers?status=proposed,approved,dispatched&limit=60") });
  const matrix = useQuery({ queryKey: ["matrix"], queryFn: () => api.get("/api/inventory/matrix"), enabled: sel != null });
  const risk = useQuery({ queryKey: ["risk", "fac", sel], queryFn: () => api.get(`/api/risk?facility_id=${sel}&limit=40`), enabled: sel != null });
  if (geo.isLoading) return <Spinner />;
  if (geo.error) return <ErrorBox error={geo.error} />;
  const feats = geo.data.features as any[];
  const markers = feats.map((f) => {
    const p = f.properties;
    const s = SEV[p.severity as Sev];
    return { id: p.id, lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], color: s.color, shape: p.type === "blood_bank" ? "B" : "",
      size: p.type === "blood_bank" ? 22 : 16 + (p.severity === "critical" ? 8 : 0), label: `${p.name} - ${p.severity}${p.worst_series ? ` (${p.worst_series})` : ""}` };
  });
  const routeData = (tr.data ?? []).map((x: any) => ({ from: [x.from_lat, x.from_lng] as [number, number], to: [x.to_lat, x.to_lng] as [number, number],
    color: x.status === "dispatched" ? "#CC79A7" : x.status === "approved" ? "#009E73" : "#0072B2", label: `${x.quantity} x ${x.abo_rh} ${x.component} (${x.status})` }));
  const selF = feats.find((f) => f.properties.id === sel)?.properties;
  const cells = matrix.data?.facilities.find((f: any) => f.facility_id === sel)?.cells ?? {};
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">{t("map")}</h1>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-1"><input type="checkbox" checked={heat} onChange={(e) => setHeat(e.target.checked)} /> Risk heat layer</label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={routes} onChange={(e) => setRoutes(e.target.checked)} /> Transfer routes</label>
          <select aria-label="Heat component" value={comp} onChange={(e) => setComp(e.target.value)} className="rounded border border-slate-300 px-2 py-1 text-sm">
            <option value="">All components</option>{COMPONENTS.map((c) => <option key={c} value={c}>{COMP_LABEL[c]}</option>)}
          </select>
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <MapView markers={markers} heat={heatQ.data?.points ?? []} routes={routeData} showHeat={heat} showRoutes={routes} onMarkerClick={(id) => setSel(Number(id))} height={580} />
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
            {(["critical", "high", "medium", "low"] as const).map((s) => <span key={s} className="flex items-center gap-1"><SevBadge sev={s} label={t(s)} /></span>)}
            <span>B = blood bank · routes: blue proposed, green approved, pink in transit · {mapsProvider}</span>
          </div>
        </div>
        <Card title={selF ? selF.name : "Select a facility"}>
          {!selF ? <p className="text-sm text-slate-500">Click a marker to see live inventory and risk.</p> : (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap items-center gap-2"><SevBadge sev={selF.severity} /> <span className="text-slate-500">{selF.code} · {selF.subtype}</span> <Freshness hours={selF.freshness_h} /></div>
              <table className="w-full text-xs">
                <thead><tr className="text-left text-slate-500"><th>Group</th>{["RBC", "PLT", "FFP"].map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{GROUPS.map((g) => <tr key={g} className="border-t border-slate-100"><td className="font-semibold">{g}</td>{["RBC", "PLT", "FFP"].map((c) => <td key={c}>{cells[`${g}|${c}`]?.usable ?? 0}</td>)}</tr>)}</tbody>
              </table>
              <div>
                <div className="mb-1 text-xs font-semibold text-slate-600">Top risks</div>
                {(risk.data?.items ?? []).slice(0, 6).map((r: any) => (
                  <Link key={r.abo_rh + r.component} to={`/forecast?f=${r.facility_id}&g=${encodeURIComponent(r.abo_rh)}&c=${r.component}`} className="flex items-center justify-between rounded px-1 py-1 hover:bg-slate-50">
                    <span><SevBadge sev={r.severity} /> {r.abo_rh} {r.component}</span><span className="text-xs">{pct(r.p_stockout_24)} / 24h · {hrs(r.tts_p50)}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

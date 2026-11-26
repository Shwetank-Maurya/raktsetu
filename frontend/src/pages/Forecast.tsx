import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Area, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, Legend, CartesianGrid } from "recharts";
import { api, enc } from "../api/client";
import { Card, ErrorBox, Select, SevBadge, Spinner, Stat } from "../components/ui";
import { COMP_LABEL, COMPONENTS, GROUPS, hrs, pct } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function Forecast() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();
  const facs = useQuery({ queryKey: ["facilities"], queryFn: () => api.get("/api/facilities") });
  const inScope = (facs.data ?? []).filter((f: any) => f.in_scope);
  const f = sp.get("f") ?? String(user?.facility_id ?? inScope[0]?.id ?? 1);
  const g = sp.get("g") ?? "O+";
  const c = sp.get("c") ?? "RBC";
  const set = (k: string, v: string) => { sp.set(k, v); setSp(sp, { replace: true }); };
  const q = useQuery({ queryKey: ["forecast", f, g, c], queryFn: () => api.get(`/api/forecasts/${f}/${enc(g)}/${c}?history_days=90`) });
  const data = useMemo(() => {
    if (!q.data) return [];
    const hist = q.data.history.map((h: any) => ({ date: h.date, actual: h.units, event: h.event ? h.units : null }));
    const fc = q.data.forecast.map((p: any) => ({ date: p.date, q50: +(p.q50 + p.scheduled).toFixed(2), mean: +(p.mean + p.scheduled).toFixed(2),
      band: [+(p.q10 + p.scheduled).toFixed(2), +(p.q90 + p.scheduled).toFixed(2)] }));
    return [...hist, ...fc];
  }, [q.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto">{t("forecast")}<span className="accent">demand, <i>with</i> uncertainty</span></h1>
        <Select label="Facility" value={f} onChange={(v) => set("f", v)} options={inScope.map((x: any) => [String(x.id), `${x.code} ${x.name}`] as [string, string])} />
        <Select label="Group" value={g} onChange={(v) => set("g", v)} options={[...GROUPS]} />
        <Select label="Component" value={c} onChange={(v) => set("c", v)} options={COMPONENTS.map((x) => [x, COMP_LABEL[x]] as [string, string])} />
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <>
          {q.data.risk && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Stat label="Severity" value={<SevBadge sev={q.data.risk.severity} />} />
              <Stat label="P(stockout) 24 / 48 / 72 h" value={`${pct(q.data.risk.p_stockout_24)} / ${pct(q.data.risk.p_stockout_48)} / ${pct(q.data.risk.p_stockout_72)}`} />
              <Stat label={`${t("tts")} (median, p10)`} value={hrs(q.data.risk.tts_p50)} hint={`10% chance within ${hrs(q.data.risk.tts_p10)}`} />
              <Stat label="Usable units" value={q.data.risk.usable_units} hint={`${q.data.risk.days_cover} days of cover`} />
              <Stat label="Confidence" value={pct(q.data.risk.confidence)} hint="freshness, interval width, history, model agreement" />
            </div>
          )}
          <Card title={`Daily demand: last 90 days and 14-day forecast with 80% interval, scheduled thalassemia units included (model: ${q.data.model ?? "n/a"})`}>
            <div className="h-80">
              <ResponsiveContainer>
                <ComposedChart data={data}>
                  <CartesianGrid stroke="#f1f5f9" />
                  <XAxis dataKey="date" fontSize={11} minTickGap={30} />
                  <YAxis fontSize={11} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Area dataKey="band" name="80% interval" fill="#56B4E9" fillOpacity={0.3} stroke="none" />
                  <Line dataKey="actual" name="Issued" stroke="#334155" dot={false} strokeWidth={1.5} />
                  <Line dataKey="q50" name="Median" stroke="#D55E00" strokeWidth={2} dot={false} />
                  <Line dataKey="mean" name="Expected demand (drives risk)" stroke="#0072B2" strokeDasharray="5 4" strokeWidth={2} dot={false} />
                  <Scatter dataKey="event" name="Event day (winsorised in training)" fill="#CC79A7" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Why this forecast? Active drivers">
            <div className="flex flex-wrap gap-2">
              {(q.data.drivers ?? []).map((d: any, i: number) => (
                <span key={i} className="rounded-full border border-[#cfc6c6] bg-brand-blush px-3 py-1 text-xs">{d.label}</span>
              ))}
              {(!q.data.drivers || q.data.drivers.length === 0) && <span className="text-sm text-[#6b6b6b]">No drivers recorded.</span>}
            </div>
            <p className="mt-2 text-xs text-[#6b6b6b]">Festival dates come from Google Calendar public holidays (static fallback); dengue/monsoon index from the season curve and Open-Meteo rainfall when available.</p>
          </Card>
        </>
      )}
    </div>
  );
}

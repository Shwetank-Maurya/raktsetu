import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, enc } from "../api/client";
import { Card, ErrorBox, PageHeader, Select, SevBadge, Skeleton, Stat } from "../components/ui";
import { COMP_LABEL, COMPONENTS, GROUPS, hrs, pct } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

const C = { actual: "#3f3f46", median: "#c0192f", mean: "#0072B2", band: "#56B4E9" };
const short = (d: string) => new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

export default function Forecast() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [sp, setSp] = useSearchParams();
  const facs = useQuery({ queryKey: ["facilities"], queryFn: () => api.get("/api/facilities") });
  const inScope = (facs.data ?? []).filter((f: any) => f.in_scope);
  const f = sp.get("f") ?? String(user?.facility_id ?? inScope[0]?.id ?? "");
  const g = sp.get("g") ?? "O+";
  const c = sp.get("c") ?? "RBC";
  const set = (k: string, v: string) => { sp.set(k, v); setSp(sp, { replace: true }); };
  const q = useQuery({ queryKey: ["forecast", f, g, c], enabled: !!f, queryFn: () => api.get(`/api/forecasts/${f}/${enc(g)}/${c}?history_days=90`) });

  const { data, today } = useMemo(() => {
    if (!q.data) return { data: [], today: null as string | null };
    const hist = q.data.history.map((h: any) => ({ date: h.date, actual: h.units }));
    const fc = q.data.forecast.map((p: any) => ({
      date: p.date,
      median: +(p.q50 + p.scheduled).toFixed(2),
      mean: +(p.mean + p.scheduled).toFixed(2),
      band: [+(p.q10 + p.scheduled).toFixed(2), +(p.q90 + p.scheduled).toFixed(2)],
    }));
    return { data: [...hist, ...fc], today: fc[0]?.date ?? null };
  }, [q.data]);

  const r = q.data?.risk;
  return (
    <div>
      <PageHeader title={t("forecast")} description="Daily demand history with a 14-day probabilistic forecast."
        actions={<>
          <Select label="Facility" value={f} onChange={(v) => set("f", v)} options={inScope.map((x: any) => [String(x.id), `${x.code} · ${x.name}`] as [string, string])} />
          <Select label="Group" value={g} onChange={(v) => set("g", v)} options={[...GROUPS]} />
          <Select label="Component" value={c} onChange={(v) => set("c", v)} options={COMPONENTS.map((x) => [x, COMP_LABEL[x]] as [string, string])} />
        </>} />
      <ErrorBox error={q.error} />
      {q.isLoading || !q.data ? <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-80" /></div> : (
        <div className="space-y-6">
          {r && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <Stat label="Severity" value={<SevBadge sev={r.severity} />} />
              <Stat label="Stockout in 24 h" value={pct(r.p_stockout_24)} hint={`48 h ${pct(r.p_stockout_48)} · 72 h ${pct(r.p_stockout_72)}`} />
              <Stat label={t("tts")} value={hrs(r.tts_p50)} hint={`10% chance within ${hrs(r.tts_p10)}`} />
              <Stat label="Usable units" value={r.usable_units} hint={`${r.days_cover} days of cover`} />
              <Stat label="Confidence" value={pct(r.confidence)} hint="Freshness, interval width, history" />
            </div>
          )}
          <Card title="Demand" description={`Last 90 days and next 14 days · model ${q.data.model ?? "n/a"} · scheduled thalassemia units included`}
            action={<div className="flex flex-wrap gap-3 text-xs text-muted">
              {[["Issued", C.actual], ["Median", C.median], ["Expected (drives risk)", C.mean], ["80% interval", C.band]].map(([l, col]) => (
                <span key={l} className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: col }} />{l}</span>
              ))}
            </div>}>
            <div className="h-80">
              <ResponsiveContainer>
                <ComposedChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke="#f0f0f2" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={short} fontSize={11} tickLine={false} axisLine={{ stroke: "#e4e4e7" }} minTickGap={36} />
                  <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip labelFormatter={(d) => short(String(d))} contentStyle={{ borderRadius: 8, border: "1px solid #e4e4e7", fontSize: 12 }} />
                  {today && <ReferenceLine x={today} stroke="#a1a1aa" strokeDasharray="3 3" label={{ value: "today", fontSize: 10, fill: "#71717a", position: "insideTopLeft" }} />}
                  <Area dataKey="band" name="80% interval" fill={C.band} fillOpacity={0.18} stroke="none" isAnimationActive={false} />
                  <Line dataKey="actual" name="Issued" stroke={C.actual} strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  <Line dataKey="median" name="Median" stroke={C.median} strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line dataKey="mean" name="Expected" stroke={C.mean} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Drivers" description="What moved this forecast">
            <div className="flex flex-wrap gap-2">
              {(q.data.drivers ?? []).map((d: any, i: number) => <span key={i} className="rounded-md border border-line bg-canvas px-2 py-1 text-xs text-body">{d.label}</span>)}
              {!q.data.drivers?.length && <span className="text-sm text-muted">No drivers recorded.</span>}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

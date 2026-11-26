import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { Card, ErrorBox, Spinner, Stat } from "../components/ui";
import { ist } from "../lib/format";
import { useI18n } from "../lib/i18n";

export default function Evaluation() {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["eval"], queryFn: () => api.get("/api/eval") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorBox error={q.error} />;
  const bt = q.data.backtest?.overall;
  const rp = q.data.replay;
  const replayBars = rp ? [
    { metric: "Wasted units", "Static threshold": rp.policy_a.wasted, RaktSetu: rp.policy_b.wasted },
    { metric: "Unmet units", "Static threshold": rp.policy_a.unmet, RaktSetu: rp.policy_b.unmet },
    { metric: "Stockout series-days", "Static threshold": rp.policy_a.stockout_days, RaktSetu: rp.policy_b.stockout_days },
  ] : [];
  const groups = q.data.backtest?.metrics ?? {};
  return (
    <div className="space-y-4">
      <div><h1 className="text-xl font-bold">{t("eval")}</h1>
        <p className="text-sm text-slate-500">All numbers are measured on synthetic ground truth (see Data Card) and recomputed by the pipeline - they are not hand-entered.</p></div>
      {bt && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="WAPE vs seasonal-naive" value={`${(bt.wape_raktsetu * 100).toFixed(1)}% vs ${(bt.wape_baseline * 100).toFixed(1)}%`} tone="low" hint={`${bt.wape_improvement_pct}% lower error (14-day horizon, rolling origin)`} />
            <Stat label="Median pinball loss" value={`${bt.pinball50_raktsetu} vs ${bt.pinball50_baseline}`} hint="lower is better" />
            <Stat label="80% interval coverage" value={`${(bt.coverage80_calibrated * 100).toFixed(1)}%`} hint={`held-out, after conformal width calibration (raw ${(bt.coverage80_raw_holdout * 100).toFixed(1)}%); target 75-85%`} />
            <Stat label="Mean bias (held-out)" value={bt.mean_bias_ratio ? `${((bt.mean_bias_ratio - 1) * 100).toFixed(0)}%` : "-"} hint="expected demand vs actual; positive = over-forecast" />
          </div>
          <Card title="Model selection per series group (pinball loss; lower is better)">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead><tr className="text-left text-slate-500"><th>Group</th><th>Chosen</th><th>seasonal naive</th><th>moving avg 28</th><th>Croston SBA</th><th>LightGBM quantile</th><th>width scale</th></tr></thead>
                <tbody>{Object.entries(groups).map(([g, m]: [string, any]) => (
                  <tr key={g} className="border-t border-slate-100"><td className="font-semibold">{g}</td><td>{q.data.backtest.chosen[g]}</td>
                    {["seasonal_naive", "moving_avg_28", "croston_sba", "lgbm_quantile"].map((k) => <td key={k} className={q.data.backtest.chosen[g] === k ? "font-bold text-emerald-700" : ""}>{m[k]?.pinball ?? "-"}</td>)}
                    <td>{q.data.backtest.conformal[g]}</td></tr>))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-slate-500">{bt.coverage_note}</p>
          </Card>
        </>
      )}
      {rp && (
        <Card title={`Closed-loop replay: ${rp.days} days, identical demand for both policies`}>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="h-64 lg:col-span-2">
              <ResponsiveContainer><BarChart data={replayBars}><XAxis dataKey="metric" fontSize={12} /><YAxis fontSize={12} /><Tooltip /><Legend />
                <Bar dataKey="Static threshold" fill="#999999" /><Bar dataKey="RaktSetu" fill="#009E73" /></BarChart></ResponsiveContainer>
            </div>
            <div className="space-y-2 text-sm">
              <div className="rounded-lg bg-emerald-50 p-3"><div className="text-2xl font-bold text-emerald-800">-{rp.improvement.wastage_reduction_pct}%</div>wastage</div>
              <div className="rounded-lg bg-emerald-50 p-3"><div className="text-2xl font-bold text-emerald-800">-{rp.improvement.unmet_reduction_pct}%</div>unmet demand (fulfilment {rp.policy_a.fulfilment_pct}% → {rp.policy_b.fulfilment_pct}%)</div>
              <div className="rounded-lg bg-slate-50 p-3 text-xs">
                Alerts: {rp.policy_a.alerts} → {rp.policy_b.alerts} ({Math.round(rp.policy_a.alerts / Math.max(1, rp.policy_b.alerts))}x fewer).
                48 h recall {rp.policy_a.alert_recall_48h} → {rp.policy_b.alert_recall_48h}; precision {rp.policy_a.alert_precision} → {rp.policy_b.alert_precision}.
                Honest limitation: remaining stockouts are mostly rare-group bursts no calibrated model can flag without alert fatigue.
              </div>
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">{rp.method}</p>
        </Card>
      )}
      <Card title="Scheduled job history (Cloud Scheduler → /internal/jobs/run-cycle)">
        <table className="w-full text-xs"><thead><tr className="text-left text-slate-500"><th>Started</th><th>Status</th><th>Duration</th><th>Series</th><th>Proposals</th><th>Trigger</th></tr></thead>
          <tbody>{q.data.job_runs.map((j: any) => (
            <tr key={j.id} className="border-t border-slate-100"><td>{ist(j.started_at)}</td><td>{j.status}</td><td>{j.stats?.duration_s ?? "-"} s</td><td>{j.stats?.risk_series ?? "-"}</td><td>{j.stats?.plan?.proposals ?? "-"}</td><td>{j.stats?.trigger ?? "-"}</td></tr>))}
          </tbody></table>
      </Card>
    </div>
  );
}

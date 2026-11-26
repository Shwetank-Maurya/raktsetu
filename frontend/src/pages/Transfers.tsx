import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Button, Card, Drawer, ErrorBox, SevBadge, Spinner, Tabs } from "../components/ui";
import { COMP_LABEL, ist } from "../lib/format";
import { useAuth } from "../lib/auth";
import { track } from "../lib/firebase";
import { useI18n } from "../lib/i18n";
import { POLL_MS } from "../lib/live";

const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const TABS = [["proposed", "Proposals"], ["approved,dispatched", "In progress"], ["received,cancelled,rejected,expired", "History"]] as const;

export default function Transfers() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<string>("proposed");
  const [open, setOpen] = useState<any>(null);
  const [onlyUrgent, setOnlyUrgent] = useState(true);
  const [ack, setAck] = useState(false);
  const q = useQuery({ queryKey: ["transfers", tab], queryFn: () => api.get(`/api/transfers?status=${tab}&limit=300`), refetchInterval: POLL_MS });
  const explain = useQuery({ queryKey: ["explain", open?.id, lang], enabled: !!open, queryFn: () => api.get(`/api/transfers/${open.id}/explain?lang=${lang}`) });
  const act = useMutation({
    mutationFn: ({ id, action, body }: { id: number; action: string; body?: object }) => api.post(`/api/transfers/${id}/${action}`, body ?? {}),
    onSuccess: (_d, v) => { track("transfer_action", { action: v.action }); qc.invalidateQueries(); setOpen(null); },
  });
  const plan = useMutation({ mutationFn: () => api.post("/api/transfers/plan", { include_substitutes: true }), onSuccess: () => qc.invalidateQueries() });
  const isNet = user?.role === "regional_coordinator" || user?.role === "admin";
  let rows: any[] = q.data ?? [];
  if (tab === "proposed") {
    rows = [...rows].sort((a, b) => (SEV_RANK[a.reason?.destination?.severity] ?? 9) - (SEV_RANK[b.reason?.destination?.severity] ?? 9) || b.quantity - a.quantity);
    if (onlyUrgent) rows = rows.filter((r) => ["critical", "high"].includes(r.reason?.destination?.severity) || (r.reason?.saves?.wastage_units ?? 0) >= 3 || r.kind === "manual");
  }
  const actions = (r: any) => {
    const b: [string, string][] = [];
    if (r.status === "proposed" && isNet) b.push(["approve", t("approve")], ["reject", t("reject")]);
    if (r.status === "approved" && (isNet || user?.facility_id === r.from_facility_id)) b.push(["dispatch", t("dispatch")], ["cancel", t("cancel")]);
    if (r.status === "dispatched" && (isNet || user?.facility_id === r.to_facility_id)) b.push(["receive", t("receive")]);
    if (r.status === "dispatched" && (isNet || user?.facility_id === r.from_facility_id)) b.push(["cancel", t("cancel")]);
    return b;
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h1>{t("transfers")}</h1><p>Optimizer proposals ranked by urgency. Every move needs a human approval.</p></div>
        {isNet && <Button onClick={() => plan.mutate()} disabled={plan.isPending}>{plan.isPending ? "Optimising..." : "Re-run optimizer"}</Button>}
      </div>
      <ErrorBox error={act.error || plan.error} />
      <div className="flex flex-wrap items-center gap-2">
        <Tabs value={tab} onChange={setTab} options={TABS.map(([k, label]) => [k, label] as [string, string])} />
        {tab === "proposed" && <label className="ml-2 flex items-center gap-1.5 text-sm text-body"><input type="checkbox" className="accent-[var(--color-accent)]" checked={onlyUrgent} onChange={(e) => setOnlyUrgent(e.target.checked)} /> Urgent and rescue only</label>}
        <span className="text-xs text-muted">{rows.length} shown</span>
      </div>
      {q.isLoading ? <Spinner /> : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted"><th>Priority</th><th>Move</th><th>From → To</th><th>ETA</th><th>Life on arrival</th><th>Saves</th><th>Status</th><th /></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-line-soft align-top">
                    <td className="py-2">{r.reason?.destination?.severity ? <SevBadge sev={r.reason.destination.severity} /> : <span className="text-xs">{r.kind}</span>}</td>
                    <td className="py-2"><b>{r.quantity} x {r.abo_rh}</b> {COMP_LABEL[r.component]}
                      {r.needs_clinician_approval && <div className="mt-0.5 rounded bg-amber-100 px-1 text-xs text-amber-900">substitute for {r.requested_for_abo_rh} - clinician sign-off</div>}
                      {r.flagged_for_review && <div className="mt-0.5 rounded bg-red-100 px-1 text-xs text-red-800">over-request flagged</div>}
                      {r.kind === "rescue" && <div className="mt-0.5 text-xs text-emerald-700">rescue near-expiry</div>}
                    </td>
                    <td className="py-2">{r.from_name}<div className="text-xs text-muted">→ {r.to_name}</div></td>
                    <td className="py-2">{Math.round(r.eta_minutes)} min<div className="text-[10px] text-faint">{r.eta_source}</div></td>
                    <td className="py-2">{Math.round(r.min_life_on_arrival_h)} h</td>
                    <td className="py-2 text-xs">{r.reason?.saves ? <>{r.reason.saves.shortage_units} short · {r.reason.saves.wastage_units} waste</> : "-"}</td>
                    <td className="py-2 text-xs">{r.status}<div className="text-faint">{ist(r.updated_at)}</div></td>
                    <td className="py-2 text-right"><Button size="sm" variant="secondary" onClick={() => { setAck(false); setOpen(r); }}>{t("why")}</Button></td>
                  </tr>
                ))}
                {rows.length === 0 && <tr><td colSpan={8} className="py-4 text-center text-muted">Nothing here.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <Drawer open={!!open} onClose={() => setOpen(null)} title={open ? `${open.quantity} x ${open.abo_rh} ${COMP_LABEL[open.component]}` : ""}>
        {open && (
          <div className="space-y-4 text-sm">
            <div className="rounded-xl bg-canvas p-3">
              {explain.isLoading ? <Spinner label="Gemini is explaining" /> : explain.data && (
                <>
                  <div className="font-semibold">{explain.data.summary}</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5">{explain.data.bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}</ul>
                  <div className="mt-2 text-[11px] text-muted">{explain.data.fallback ? "Template explanation (Gemini unavailable or failed the number check)" : "Explained by Gemini from the optimizer's reason JSON; every number verified against it."}</div>
                </>
              )}
            </div>
            <details open><summary className="cursor-pointer font-semibold">Optimizer reasoning (raw)</summary>
              <pre className="mt-2 max-h-80 overflow-auto rounded bg-slate-900 p-3 text-[11px] text-slate-100">{JSON.stringify(open.reason, null, 2)}</pre>
            </details>
            {open.needs_clinician_approval && (
              <label className="flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-amber-900">
                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1" />
                <span>Compatible substitution ({open.abo_rh} for {open.requested_for_abo_rh}). I confirm a clinician has reviewed and signed off.</span>
              </label>
            )}
            <div className="flex flex-wrap gap-2">
              {actions(open).map(([a, label]) => (
                <Button key={a} variant={a === "approve" || a === "receive" || a === "dispatch" ? "primary" : "secondary"}
                  disabled={act.isPending || (a === "approve" && open.needs_clinician_approval && !ack)}
                  onClick={() => act.mutate({ id: open.id, action: a, body: a === "approve" ? { clinician_ack: ack } : {} })}>{label}</Button>
              ))}
            </div>
            <ErrorBox error={act.error} />
          </div>
        )}
      </Drawer>
    </div>
  );
}

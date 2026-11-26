import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Button, Card, ErrorBox, Select } from "../components/ui";
import { COMP_LABEL, COMPONENTS, GROUPS } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function Inventory() {
  const { t } = useI18n();
  const { user } = useAuth();
  const qc = useQueryClient();
  const facs = useQuery({ queryKey: ["facilities"], queryFn: () => api.get("/api/facilities") });
  const inScope = (facs.data ?? []).filter((f: any) => f.in_scope);
  const [fid, setFid] = useState(String(user?.facility_id ?? ""));
  const [type, setType] = useState("receive");
  const [g, setG] = useState("O+");
  const [c, setC] = useState("RBC");
  const [qty, setQty] = useState(1);
  const [emergency, setEmergency] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const m = useMutation({
    mutationFn: () => api.post("/api/inventory/events", { type, facility_id: Number(fid || inScope[0]?.id), abo_rh: g, component: c, quantity: qty, emergency, source: "ui" }),
    onSuccess: (d) => { setLog((l) => [`${new Date().toLocaleTimeString("en-IN")}: ${type} ${d.count} x ${g} ${c} (event #${d.event_id})`, ...l]); qc.invalidateQueries(); },
  });
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div><h1 className="text-xl font-bold">{t("inventory")}</h1>
        <p className="text-sm text-slate-500">Every change appends to the ledger with an Idempotency-Key, so a double-click or network retry never double-counts. Issues use FEFO automatically. Open the Availability matrix in another browser to watch it update.</p></div>
      <Card>
        <div className="grid gap-3 sm:grid-cols-3">
          <Select label="Facility" value={fid} onChange={setFid} options={inScope.map((f: any) => [String(f.id), `${f.code} ${f.name}`] as [string, string])} />
          <Select label="Event" value={type} onChange={setType} options={[["receive", "Receive (new units)"], ["issue", "Issue to patient (FEFO)"], ["discard", "Discard"]]} />
          <Select label="Blood group" value={g} onChange={setG} options={[...GROUPS]} />
          <Select label="Component" value={c} onChange={setC} options={COMPONENTS.map((x) => [x, COMP_LABEL[x]] as [string, string])} />
          <label className="flex flex-col gap-1 text-xs text-slate-600">Quantity<input type="number" min={1} max={200} value={qty} onChange={(e) => setQty(Number(e.target.value))} className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" /></label>
          {type === "issue" && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={emergency} onChange={(e) => setEmergency(e.target.checked)} /> Emergency issue</label>}
        </div>
        <div className="mt-3"><Button onClick={() => m.mutate()} disabled={m.isPending}>Record</Button></div>
        <ErrorBox error={m.error} />
      </Card>
      {log.length > 0 && <Card title="This session"><ul className="space-y-1 text-sm">{log.map((l, i) => <li key={i}>{l}</li>)}</ul></Card>}
    </div>
  );
}

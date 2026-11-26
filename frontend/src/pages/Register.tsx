import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Button, Card, ErrorBox, Select } from "../components/ui";
import { COMPONENTS, GROUPS } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function Register() {
  const { t } = useI18n();
  const { user } = useAuth();
  const facs = useQuery({ queryKey: ["facilities"], queryFn: () => api.get("/api/facilities") });
  const [fid, setFid] = useState(String(user?.facility_id ?? ""));
  const [rows, setRows] = useState<any[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const extract = useMutation({
    mutationFn: () => { const fd = new FormData(); fd.append("facility_id", fid); fd.append("image", file!); return api.upload("/api/register/extract", fd); },
    onSuccess: (d) => setRows(d.rows),
  });
  const commit = useMutation({ mutationFn: () => api.post("/api/register/commit", { facility_id: Number(fid), rows: rows.map(({ row: _r, issues: _i, low_confidence_fields: _l, blocks_commit: _b, confidence: _c, ...rest }) => rest) }) });
  const edit = (i: number, k: string, v: string) => setRows((rs) => rs.map((r, j) => j !== i ? r : { ...r, [k]: k === "quantity" ? Number(v) : v, low_confidence_fields: r.low_confidence_fields.filter((f: string) => f !== k) }));
  const blocked = rows.some((r) => r.low_confidence_fields.length || r.issues.length);
  const inScope = (facs.data ?? []).filter((f: any) => f.in_scope);
  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div><h1 className="text-xl font-bold">{t("register")}: photo of a paper stock register → structured inventory</h1>
        <p className="text-sm text-slate-500">Gemini vision extracts rows with a strict JSON schema and per-field confidence. Low-confidence fields are highlighted and block commit until a human edits them. Nothing is committed automatically.</p></div>
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Facility" value={fid} onChange={setFid} options={[["", "choose"], ...inScope.map((f: any) => [String(f.id), `${f.code} ${f.name}`] as [string, string])]} />
          <label className="text-xs text-slate-600">Register photo<input type="file" accept="image/*" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block text-sm" /></label>
          <Button onClick={() => extract.mutate()} disabled={!file || !fid || extract.isPending}>{extract.isPending ? "Reading with Gemini..." : "Extract"}</Button>
        </div>
        <ErrorBox error={extract.error} />
      </Card>
      {rows.length > 0 && (
        <Card title="Review extracted rows">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500"><th>Group</th><th>Component</th><th>Qty</th><th>Donation ID</th><th>Collected</th><th>Expires</th><th>Issues</th></tr></thead>
            <tbody>{rows.map((r, i) => {
              const low = (k: string) => (r.low_confidence_fields.includes(k) ? "ring-2 ring-[#E69F00] bg-amber-50" : "");
              return (
                <tr key={i} className="border-t border-slate-100">
                  <td><select value={r.abo_rh} onChange={(e) => edit(i, "abo_rh", e.target.value)} className={`rounded border px-1 ${low("abo_rh")}`}>{GROUPS.map((g) => <option key={g}>{g}</option>)}</select></td>
                  <td><select value={r.component} onChange={(e) => edit(i, "component", e.target.value)} className={`rounded border px-1 ${low("component")}`}>{COMPONENTS.map((c) => <option key={c}>{c}</option>)}</select></td>
                  <td><input type="number" value={r.quantity} onChange={(e) => edit(i, "quantity", e.target.value)} className={`w-16 rounded border px-1 ${low("quantity")}`} /></td>
                  <td><input value={r.donation_id ?? ""} onChange={(e) => edit(i, "donation_id", e.target.value)} className="w-28 rounded border px-1" /></td>
                  <td><input type="date" value={r.collected_on ?? ""} onChange={(e) => edit(i, "collected_on", e.target.value)} className={`rounded border px-1 ${low("collected_on")}`} /></td>
                  <td><input type="date" value={r.expires_on ?? ""} onChange={(e) => edit(i, "expires_on", e.target.value)} className={`rounded border px-1 ${low("expires_on")}`} /></td>
                  <td className="text-xs text-red-700">{r.issues.join("; ")}</td>
                </tr>
              );
            })}</tbody>
          </table>
          <div className="mt-3 flex items-center gap-3">
            <Button onClick={() => commit.mutate()} disabled={blocked || commit.isPending}>Commit reviewed rows</Button>
            {blocked && <span className="text-xs text-amber-800">Fix highlighted fields and issues first.</span>}
            {commit.data && <span className="text-sm text-emerald-700">Committed {commit.data.units} units.</span>}
          </div>
          <ErrorBox error={commit.error} />
        </Card>
      )}
    </div>
  );
}

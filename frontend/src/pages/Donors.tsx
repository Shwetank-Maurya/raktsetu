import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Button, Card, ErrorBox, Select } from "../components/ui";
import { GROUPS } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

export default function Donors() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const facs = useQuery({ queryKey: ["facilities"], queryFn: () => api.get("/api/facilities") });
  const [fid, setFid] = useState(String(user?.facility_id ?? 26));
  const [g, setG] = useState("O-");
  const [radius, setRadius] = useState(15);
  const [language, setLanguage] = useState<string>(lang);
  const draft = useMutation({ mutationFn: () => api.read("/api/donors/campaign/draft", { facility_id: Number(fid), abo_rh: g, component: "RBC", radius_km: radius, language, max_donors: 100 }) });
  const inScope = (facs.data ?? []).filter((f: any) => f.in_scope);
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div><h1 className="text-xl font-bold">{t("donors")}</h1>
        <p className="text-sm text-slate-500">Eligible donors are selected in code (consent, not opted out, donation interval, distance). Gemini only writes the message. First names only; phones stay hashed on the server. Sending is simulated in the demo.</p></div>
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Facility" value={fid} onChange={setFid} options={inScope.map((f: any) => [String(f.id), `${f.code} ${f.name}`] as [string, string])} />
          <Select label="Blood group" value={g} onChange={setG} options={[...GROUPS]} />
          <Select label="Radius" value={String(radius)} onChange={(v) => setRadius(Number(v))} options={["5", "10", "15", "25", "40"].map((x) => [x, `${x} km`] as [string, string])} />
          <Select label="Language" value={language} onChange={setLanguage} options={[["hi", "हिन्दी"], ["en", "English"]]} />
          <Button onClick={() => draft.mutate()} disabled={draft.isPending}>{draft.isPending ? "Drafting..." : "Draft appeal"}</Button>
        </div>
        <ErrorBox error={draft.error} />
      </Card>
      {draft.data && (
        <Card title={`${draft.data.eligible_donors} eligible ${draft.data.abo_rh} donors near ${draft.data.facility}`}>
          <div className="rounded-lg bg-slate-50 p-3 text-sm">{draft.data.template}</div>
          <div className="mt-1 text-[11px] text-slate-500">{draft.data.fallback ? "Template message (Gemini unavailable)" : "Drafted by Gemini, checked for placeholder and opt-out line"} · {draft.data.sending}</div>
          <h3 className="mt-3 text-xs font-semibold text-slate-600">Previews</h3>
          <ul className="mt-1 space-y-2 text-sm">{draft.data.previews.map((p: any) => <li key={p.donor_id} className="rounded border border-slate-200 p-2"><span className="text-xs text-slate-500">{p.first_name} · {p.distance_km} km</span><div>{p.message}</div></li>)}</ul>
          <p className="mt-2 text-xs text-slate-500">{draft.data.privacy}</p>
        </Card>
      )}
    </div>
  );
}

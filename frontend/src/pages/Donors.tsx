import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { HeartHandshake, MapPin, MessageSquareText, ShieldCheck, Users } from "lucide-react";
import { endpoints } from "../api/endpoints";

import { Button, Card, ErrorBox, Select, Spinner } from "../components/ui";
import { GROUPS } from "../lib/format";
import { useAuth } from "../lib/auth-context";
import { useI18n } from "../lib/i18n-context";

export default function Donors() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const facs = useQuery({ queryKey: ["facilities"], queryFn: endpoints.facilities });
  const [fidSel, setFid] = useState<string>(user?.facility_id ? String(user.facility_id) : "");
  const [g, setG] = useState("O-");
  const [radius, setRadius] = useState(15);
  const [language, setLanguage] = useState<string>(lang);
  const draft = useMutation({ mutationFn: () => endpoints.campaign({ facility_id: Number(fid), abo_rh: g, component: "RBC", radius_km: radius, language, max_donors: 100 }) });
  const inScope = (facs.data ?? []).filter((f) => f.in_scope);
  const fid = fidSel || String(inScope.find((f) => f.type === "blood_bank")?.id ?? inScope[0]?.id ?? "");
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="relative overflow-hidden rounded-2xl border border-line bg-white px-6 py-7 sm:px-8">
        <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-accent-soft blur-2xl" aria-hidden />
        <div className="relative grid gap-5 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <span className="inline-flex items-center gap-2 text-xs font-medium text-accent"><HeartHandshake size={15} /> CONSENT-BASED OUTREACH</span>
            <h1 className="mt-2">{t("donors")}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">Create a respectful, local appeal when a blood group needs attention. Eligibility is calculated on the server; Gemini only helps write the message.</p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg border border-line-soft bg-canvas px-3 py-2"><Users size={15} className="mx-auto text-accent" /><span className="mt-1 block text-muted">Eligible only</span></div>
            <div className="rounded-lg border border-line-soft bg-canvas px-3 py-2"><MapPin size={15} className="mx-auto text-accent" /><span className="mt-1 block text-muted">Nearby donors</span></div>
            <div className="rounded-lg border border-line-soft bg-canvas px-3 py-2"><ShieldCheck size={15} className="mx-auto text-accent" /><span className="mt-1 block text-muted">Privacy first</span></div>
          </div>
        </div>
      </section>

      <Card title="Draft an appeal" description="Choose the need. Review every preview before any outreach.">
        <div className="flex flex-wrap items-end gap-3">
          <Select label="Facility" value={fid} onChange={setFid} options={inScope.map((f) => [String(f.id), `${f.code} ${f.name}`] as [string, string])} />
          <Select label="Blood group" value={g} onChange={setG} options={[...GROUPS]} />
          <Select label="Radius" value={String(radius)} onChange={(v) => setRadius(Number(v))} options={["5", "10", "15", "25", "40"].map((x) => [x, `${x} km`] as [string, string])} />
          <Select label="Language" value={language} onChange={setLanguage} options={[["hi", "हिन्दी"], ["en", "English"]]} />
          <Button onClick={() => draft.mutate()} disabled={draft.isPending || !fid}>{draft.isPending ? "Drafting..." : "Draft appeal"}</Button>
        </div>
        <ErrorBox error={draft.error} />
      </Card>
      {facs.isLoading && <Spinner label="Loading facilities" />}
      {draft.data && (
        <Card title="Appeal ready for review" description={`${draft.data.eligible_donors} eligible ${draft.data.abo_rh} donors near ${draft.data.facility}`} action={<span className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft px-2 py-1 text-xs font-medium text-accent-strong"><MessageSquareText size={13} /> {draft.data.sending}</span>}>
          <div className="rounded-xl border border-line-soft bg-canvas p-4 text-sm leading-relaxed text-body">{draft.data.template}</div>
          <div className="mt-2 text-[11px] text-muted">{draft.data.fallback ? "Safe template used while Gemini is unavailable." : "Gemini draft checked for a first-name placeholder and opt-out line."}</div>
          <div className="mt-5 flex items-center justify-between"><h3 className="text-sm font-semibold text-ink">Recipient previews</h3><span className="text-xs text-muted">No contact details are shown</span></div>
          <ul className="mt-2 grid gap-2 sm:grid-cols-2">{draft.data.previews.map((p) => <li key={p.donor_id} className="rounded-lg border border-line p-3 text-sm"><div className="flex items-center justify-between"><span className="font-medium text-ink">{p.first_name}</span><span className="inline-flex items-center gap-1 text-xs text-muted"><MapPin size={12} /> {p.distance_km} km</span></div><div className="mt-2 text-xs leading-relaxed text-body">{p.message}</div></li>)}</ul>
          <p className="mt-4 flex items-start gap-2 border-t border-line-soft pt-3 text-xs leading-relaxed text-muted"><ShieldCheck size={14} className="mt-0.5 shrink-0 text-success" />{draft.data.privacy}</p>
        </Card>
      )}
    </div>
  );
}

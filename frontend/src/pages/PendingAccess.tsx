import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, MailCheck, ShieldCheck, XCircle } from "lucide-react";
import { api } from "../api/client";
import { Button, ErrorBox, inputCls, Select, Spinner, Tabs } from "../components/ui";
import { useAuth } from "../lib/auth";
import { auth } from "../lib/firebase";

/** Shown to signed-up accounts that have no role yet: request access, then wait for approval. */
export default function PendingAccess() {
  const { user, refreshAccess, logout } = useAuth();
  const qc = useQueryClient();
  const mine = useQuery({ queryKey: ["access-mine"], queryFn: () => api.get("/api/access-requests/mine") });
  const facs = useQuery({ queryKey: ["public-facilities"], queryFn: () => api.get("/api/public/facilities"), staleTime: 3_600_000 });
  const [role, setRole] = useState("hospital_user");
  const [fid, setFid] = useState("");
  const [name, setName] = useState("");
  // The display name can arrive after first render (token refresh after sign-up); prefill once known.
  useEffect(() => { if (!name && user?.name && !user.name.includes("@")) setName(user.name); }, [user?.name]); // eslint-disable-line react-hooks/exhaustive-deps
  const [note, setNote] = useState("");
  const [checkMsg, setCheckMsg] = useState<string | null>(null);
  const [checkError, setCheckError] = useState<unknown>(null);
  const submit = useMutation({
    mutationFn: () => api.post("/api/access-requests", { name, requested_role: role, facility_id: Number(fid), note: note || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["access-mine"] }),
  });
  const check = async () => {
    setCheckMsg(null); setCheckError(null);
    try {
      const r = await refreshAccess();
      if (r === "pending") setCheckMsg("Still waiting for approval. You can safely check again later.");
      else if (r) setCheckMsg("Access approved. Opening your workspace…");
      else setCheckError(new Error("We could not refresh your access. Please sign in again."));
    } catch (e) { setCheckError(e); }
  };

  const options = (facs.data ?? []).filter((f: any) => role === "bank_manager" ? f.type === "blood_bank" : f.type === "hospital");
  const req = mine.data;
  const verified = auth?.currentUser?.emailVerified;
  const onSubmit = (e: FormEvent) => { e.preventDefault(); submit.mutate(); };

  if (mine.isLoading) return <Spinner />;
  return (
    <div className="grid-bg flex min-h-[calc(100vh-8.5rem)] items-center justify-center px-4 py-16">
      <div className="w-full max-w-md rounded-2xl border border-line bg-white p-7">
        {req && req.status !== "rejected" ? (
          <>
            <div className="flex items-center gap-2 text-sm font-medium text-[#8a5800]"><Clock size={16} /> Step 3 of 3 · waiting for approval</div>
            <h1 className="mt-3 text-xl font-semibold text-ink">Your request has been sent</h1>
            <p className="mt-2 text-sm text-muted">A regional coordinator will review access for <b className="text-ink">{req.name}</b> as{" "}
              {req.requested_role === "bank_manager" ? "blood bank staff" : "hospital staff"} at <b className="text-ink">{req.facility_name}</b>.</p>
            <div className="mt-6 flex gap-2">
              <Button onClick={check}>Check again</Button>
              <Button variant="secondary" onClick={logout}>Sign out</Button>
            </div>
            {checkMsg && <p className="mt-3 text-xs text-muted">{checkMsg}</p>}
            <ErrorBox error={checkError} />
          </>
        ) : (
          <>
            {req?.status === "rejected" && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-accent-soft px-3 py-2 text-sm text-accent-strong">
                <XCircle size={16} className="mt-0.5 shrink-0" /> Your previous request was declined{req.decision_note ? `: ${req.decision_note}` : "."} You can submit a new one.
              </div>
            )}
            <div className="flex items-center gap-2 text-sm font-medium text-accent"><ShieldCheck size={16} /> Step 2 of 3 · request workspace access</div>
            <h1 className="mt-3 text-xl font-semibold text-ink">Request access</h1>
            <p className="mt-1 text-sm text-muted">Tell us where you work. You will see that facility's data once approved.</p>
            <form onSubmit={onSubmit} className="mt-6 space-y-3">
              <label className="block text-xs font-medium text-body">Full name
                <input className={`${inputCls} mt-1`} required minLength={2} value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <div className="text-xs font-medium text-body">I work at a
                <div className="mt-1"><Tabs value={role} onChange={(v) => { setRole(v); setFid(""); }} options={[["hospital_user", "Hospital"], ["bank_manager", "Blood bank"]]} /></div>
              </div>
              <Select label="Facility" value={fid} onChange={setFid}
                options={[["", "Select your facility"], ...options.map((f: any) => [String(f.id), `${f.name} · ${f.district ?? ""}`] as [string, string])]} />
              <label className="block text-xs font-medium text-body">Note for the coordinator <span className="font-normal text-faint">(optional)</span>
                <input className={`${inputCls} mt-1`} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Transfusion officer, night shift" />
              </label>
              <Button type="submit" className="w-full" disabled={!fid || name.length < 2 || submit.isPending}>{submit.isPending ? "Sending…" : "Send request"}</Button>
              <ErrorBox error={submit.error} />
            </form>
            <button onClick={logout} className="mt-4 text-xs text-muted hover:text-ink">Sign out</button>
          </>
        )}
        {verified === false && (
          <p className="mt-6 flex items-center gap-2 border-t border-line-soft pt-4 text-xs text-muted"><MailCheck size={14} /> We sent a verification link to your email.</p>
        )}
        {req && req.status !== "rejected" && <p className="mt-4 flex items-center gap-2 text-xs text-muted"><CheckCircle2 size={14} className="text-success" /> No patient or inventory data is available until your request is approved.</p>}
      </div>
    </div>
  );
}

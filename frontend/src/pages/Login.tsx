import { useState } from "react";
import { Droplet } from "lucide-react";
import { Button, ErrorBox } from "../components/ui";
import { useAuth } from "../lib/auth";
import { firebaseEnabled, track } from "../lib/firebase";

const DEMO = [
  { who: "coordinator", title: "Regional coordinator", desc: "Whole Delhi network: map, optimizer, approvals, stress test" },
  { who: "bank", title: "Blood bank manager", desc: "Delhi Central Blood Bank: stock, expiry, donor appeals, dispatch" },
  { who: "hospital", title: "Hospital transfusion officer", desc: "Sanjeevani General Hospital only: own stock, nearby availability, receive" },
];

export default function Login() {
  const { demoLogin, emailLogin, googleLogin } = useAuth();
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const run = async (fn: () => Promise<void>, ev: string) => {
    setBusy(true); setErr(null);
    try { await fn(); track("login", { method: ev }); } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-rose-50 to-slate-100 p-4">
      <div className="w-full max-w-xl rounded-2xl bg-white p-8 shadow-lg">
        <div className="mb-6 flex items-center gap-3">
          <Droplet size={36} className="text-rose-700" fill="currentColor" />
          <div>
            <h1 className="text-2xl font-bold text-rose-800">RaktSetu</h1>
            <p className="text-sm text-slate-600">Predict blood shortages before they become emergencies.</p>
          </div>
        </div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Try a demo role</h2>
        <div className="grid gap-2">
          {DEMO.map((d) => (
            <button key={d.who} disabled={busy} onClick={() => run(() => demoLogin(d.who), `demo_${d.who}`)}
              className="rounded-xl border border-slate-200 p-3 text-left hover:border-rose-400 hover:bg-rose-50 focus-visible:ring-2 focus-visible:ring-rose-500">
              <div className="font-semibold">{d.title}</div>
              <div className="text-xs text-slate-500">{d.desc}</div>
            </button>
          ))}
        </div>
        {firebaseEnabled && (
          <form className="mt-6 space-y-2 border-t border-slate-200 pt-4" onSubmit={(e) => { e.preventDefault(); run(() => emailLogin(email, pw), "password"); }}>
            <h2 className="text-sm font-semibold text-slate-700">Staff sign-in (Firebase Auth)</h2>
            <input aria-label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <input aria-label="Password" type="password" required value={pw} onChange={(e) => setPw(e.target.value)} placeholder="password" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            <div className="flex gap-2">
              <Button type="submit" disabled={busy}>Sign in</Button>
              <Button variant="secondary" disabled={busy} onClick={() => run(googleLogin, "google")}>Sign in with Google</Button>
            </div>
          </form>
        )}
        <div className="mt-4"><ErrorBox error={err} /></div>
        <p className="mt-6 text-xs text-slate-500">All data is synthetic. Decision support only - not a medical device; humans approve every transfer.</p>
      </div>
    </div>
  );
}

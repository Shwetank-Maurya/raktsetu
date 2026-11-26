import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, ErrorBox, inputCls } from "../components/ui";
import { DEMO_ACCOUNTS, useAuth } from "../lib/auth";
import { firebaseEnabled, track } from "../lib/firebase";
import { usePublicSummary } from "../lib/summary";

const GOOGLE = import.meta.env.VITE_AUTH_GOOGLE === "true";

export default function Login() {
  const { emailLogin, googleLogin, resetPassword, demoLogin } = useAuth();
  const [sp] = useSearchParams();
  const { data: sum } = usePublicSummary();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [note, setNote] = useState<string | null>(null);

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key); setErr(null); setNote(null);
    try { await fn(); track("login", { method: key }); } catch (e) { setErr(e); } finally { setBusy(null); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); run("password", () => emailLogin(email, pw)); };
  const scope = (who: string) => sum?.demo_roles?.[who]?.scope;

  return (
    <div className="grid-bg flex min-h-[calc(100vh-8.5rem)] items-center justify-center px-4 py-16">
      <div className="w-full max-w-sm">
        <div className="rounded-2xl border border-line bg-white p-7 shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
          <h1 className="text-xl font-semibold text-ink">Sign in</h1>
          <p className="mt-1 text-sm text-muted">{firebaseEnabled ? "Use your RaktSetu account." : "Firebase is not configured; using local demo sign-in."}</p>

          {firebaseEnabled && (
            <form onSubmit={submit} className="mt-6 space-y-3">
              <label className="block text-xs font-medium text-body">Email
                <input className={`${inputCls} mt-1`} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </label>
              <label className="block text-xs font-medium text-body">
                <span className="flex justify-between">Password
                  <button type="button" className="font-normal text-muted hover:text-ink"
                    onClick={() => email ? run("reset", async () => { await resetPassword(email); setNote("Password reset email sent."); }) : setNote("Enter your email first.")}>Forgot?</button>
                </span>
                <input className={`${inputCls} mt-1`} type="password" autoComplete="current-password" required value={pw} onChange={(e) => setPw(e.target.value)} />
              </label>
              <Button type="submit" className="w-full" disabled={!!busy}>{busy === "password" ? "Signing in…" : "Sign in"}</Button>
              {GOOGLE && <Button variant="secondary" className="w-full" disabled={!!busy} onClick={() => run("google", googleLogin)}>Continue with Google</Button>}
            </form>
          )}

          <div className="mt-4 space-y-2"><ErrorBox error={err} />{note && <p className="text-xs text-muted">{note}</p>}</div>

          <div className="mt-6 border-t border-line-soft pt-5">
            <p className="text-xs font-medium text-muted">Demo accounts</p>
            <div className="mt-2 grid gap-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button key={a.who} disabled={!!busy} onClick={() => run(a.who, () => demoLogin(a.who))}
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm hover:border-ink/30 hover:bg-canvas disabled:opacity-60 ${sp.get("role") === a.who ? "border-ink/30" : "border-line"}`}>
                  <span className="font-medium text-ink">{a.label}</span>
                  <span className="truncate pl-3 text-xs text-muted">{busy === a.who ? "Signing in…" : scope(a.who) ?? ""}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-6 text-center text-sm text-muted">New to RaktSetu? <Link to="/signup" className="font-medium text-ink hover:underline">Create an account</Link></p>
      </div>
    </div>
  );
}

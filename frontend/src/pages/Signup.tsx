import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Mail, ShieldCheck, UserRoundPlus } from "lucide-react";
import { Button, ErrorBox, inputCls } from "../components/ui";
import { useAuth } from "../lib/auth";
import { firebaseEnabled, track } from "../lib/firebase";

const STEPS = [
  { title: "Create your account", note: "Use your work email and choose a password." },
  { title: "Choose your facility and role", note: "We will ask for this straight after sign-up." },
  { title: "Start working", note: "A regional coordinator approves access to protect patient data." },
];

export default function Signup() {
  const { signup } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await signup(name, email, pw); track("sign_up", { method: "password" }); } catch (x) { setErr(x); } finally { setBusy(false); }
  };

  return (
    <div className="grid-bg flex min-h-[calc(100vh-8.5rem)] items-center justify-center px-4 py-16">
      <div className="grid w-full max-w-4xl items-center gap-10 lg:grid-cols-[1fr_400px]">
        <div className="hidden lg:block">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">Join your blood network</h1>
          <p className="mt-3 max-w-md text-muted">Hospital and blood bank staff get a live view of stock, risk and transfers for their facility.</p>
          <ol className="mt-8 space-y-4">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex items-start gap-3 text-sm">
                <span className={`grid h-7 w-7 place-items-center rounded-full text-xs font-semibold ${i === 0 ? "bg-ink text-white" : "border border-line bg-white text-muted"}`}>{i + 1}</span>
                <span><span className={i === 0 ? "font-medium text-ink" : "text-muted"}>{s.title}</span><span className="mt-0.5 block text-xs text-faint">{s.note}</span></span>
              </li>
            ))}
          </ol>
          <div className="mt-8 space-y-2 text-xs text-muted">
            <p className="flex items-center gap-2"><ShieldCheck size={14} className="text-success" /> Accounts see only their own facility until a coordinator approves access.</p>
            <p className="flex items-center gap-2"><Mail size={14} className="text-success" /> We will send a verification email after you create your account.</p>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-white p-7">
          <h2 className="text-xl font-semibold text-ink">Create account</h2>
          <p className="mt-1 text-sm text-muted">Already have one? <Link to="/login" className="text-ink underline-offset-2 hover:underline">Sign in</Link></p>
          {!firebaseEnabled ? (
            <div className="mt-6 rounded-xl border border-line bg-canvas p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-ink"><UserRoundPlus size={16} className="text-accent" /> Account creation is not enabled in this demo</div>
              <p className="mt-2 text-sm leading-relaxed text-muted">This local preview uses protected demo accounts. Use one to explore the complete staff workflow, or configure Firebase Authentication to enable real sign-ups.</p>
              <Link to="/login" className="mt-4 inline-flex h-9 items-center rounded-lg bg-ink px-3.5 text-sm font-medium text-white hover:bg-black">Open demo sign-in</Link>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-3">
              <label className="block text-xs font-medium text-body">Full name
                <input className={`${inputCls} mt-1`} required minLength={2} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="block text-xs font-medium text-body">Work email
                <input className={`${inputCls} mt-1`} type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </label>
              <label className="block text-xs font-medium text-body">Password
                <input className={`${inputCls} mt-1`} type="password" required minLength={8} autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
                <span className="mt-1 block font-normal text-faint">At least 8 characters.</span>
              </label>
              <Button type="submit" className="w-full" disabled={busy}>{busy ? "Creating account…" : "Create account and continue"}</Button>
              <ErrorBox error={err} />
              <p className="text-xs text-faint">Next, you will select your facility and role. By creating an account you agree that RaktSetu is decision support only.</p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

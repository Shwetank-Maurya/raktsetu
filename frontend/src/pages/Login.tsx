import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Building2, ChevronRight, Hospital, Lock, ShieldCheck, Users } from "lucide-react";
import { api } from "../api/client";
import Art from "../components/Art";
import { Button, ErrorBox } from "../components/ui";
import { useAuth } from "../lib/auth";
import { firebaseEnabled, track } from "../lib/firebase";

const DEMO = [
  { who: "coordinator", icon: Users, title: "Regional coordinator", sees: "Whole Delhi network", desc: "Risk map, optimizer approvals, stress test, copilot" },
  { who: "bank", icon: Building2, title: "Blood bank manager", sees: "Delhi Central Blood Bank", desc: "Stock and expiry, rescue moves, dispatch, donor appeals" },
  { who: "hospital", icon: Hospital, title: "Hospital transfusion officer", sees: "Sanjeevani General Hospital only", desc: "Own countdown, nearby availability, receive transfers" },
];

export default function Login() {
  const { demoLogin, emailLogin, googleLogin } = useAuth();
  const [sp] = useSearchParams();
  const pre = sp.get("role");
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const sum = useQuery({ queryKey: ["public-summary"], queryFn: () => api.get("/api/public/summary"), staleTime: 60_000 });
  const run = async (fn: () => Promise<void>, ev: string) => {
    setBusy(ev); setErr(null);
    try { await fn(); track("login", { method: ev }); } catch (e) { setErr(e); } finally { setBusy(null); }
  };
  const ordered = pre ? [...DEMO].sort((a, b) => (a.who === pre ? -1 : b.who === pre ? 1 : 0)) : DEMO;
  return (
    <div className="grid lg:min-h-[calc(100vh-180px)] lg:grid-cols-[1.05fr_1fr]">
      {/* Left: brand panel */}
      <section className="relative overflow-hidden bg-linear-to-br from-brand-sky via-[#1556c4] to-brand-blue px-6 py-14 text-white lg:px-14">
        <Art kind="network" palette={["#0b3fa8", "#1556c4"]} className="absolute inset-0 opacity-20" />
        <div className="relative max-w-xl">
          <nav aria-label="Breadcrumb" className="text-sm text-white/80"><Link to="/" className="hover:underline">Home</Link> <span className="mx-1">/</span> Sign in</nav>
          <h1 className="mt-6 !text-white">
            <span className="block text-5xl font-bold leading-none tracking-[-0.05em] lg:text-6xl">Every unit counts.</span>
            <span className="mt-1 block font-serif text-4xl font-light lg:text-[3.4rem]">See shortages <i>coming</i></span>
          </h1>
          <p className="mt-6 text-lg text-white/90">Sign in to see a live, synthetic Delhi network: forecasts, time-to-stockout countdowns and transfers waiting for your approval.</p>
          <div className="mt-8 grid grid-cols-3 gap-3">
            {[["Facilities", sum.data?.facilities ?? "-"], ["Series watched", sum.data?.series_monitored ?? "-"],
              ["Critical now", sum.data?.severity_counts?.critical ?? 0]].map(([k, v]) => (
              <div key={String(k)} className="rounded-br-2xl bg-white/12 p-4 ring-1 ring-white/25 backdrop-blur-sm">
                <div className="text-3xl font-bold tracking-tight">{String(v)}</div><div className="text-xs uppercase tracking-wider text-white/80">{k}</div>
              </div>
            ))}
          </div>
          <ul className="mt-8 space-y-2 text-[15px]">
            {["Humans approve every transfer", "Every AI number is checked against live data", "No patient data; donors are consent-based"].map((x) => (
              <li key={x} className="flex items-center gap-2"><ShieldCheck size={18} /> {x}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* Right: sign in */}
      <section className="flex items-center justify-center bg-brand-blush px-6 py-14">
        <div className="w-full max-w-xl">
          <h2 className="text-4xl font-bold leading-none tracking-[-0.045em] text-brand-plum-dark">Sign in</h2>
          <p className="font-serif text-3xl font-light text-brand-ink">choose a demo role</p>
          <p className="mt-3 text-sm">No account needed. Each role sees only what it is allowed to see.</p>
          <div className="mt-6 grid gap-3">
            {ordered.map((d) => (
              <button key={d.who} disabled={!!busy} onClick={() => run(() => demoLogin(d.who), `demo_${d.who}`)}
                className={clsx("group flex items-center gap-4 rounded-br-[1.75rem] bg-white p-5 text-left ring-1 transition hover:ring-2 hover:ring-brand-plum focus-visible:ring-2 focus-visible:ring-brand-plum disabled:opacity-60",
                  pre === d.who ? "ring-2 ring-brand-plum" : "ring-[#e7e2e2]")}>
                <span className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-linear-to-br from-brand-crimson to-brand-plum text-white"><d.icon size={26} /></span>
                <span className="flex-1">
                  <span className="block text-lg font-bold text-brand-ink">{d.title}</span>
                  <span className="block text-sm font-semibold text-brand-plum">{d.sees}</span>
                  <span className="block text-sm">{d.desc}</span>
                </span>
                {busy === `demo_${d.who}` ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand-plum border-t-transparent" />
                  : <ChevronRight className="text-brand-plum transition-transform group-hover:translate-x-1" strokeWidth={3} />}
              </button>
            ))}
          </div>
          {firebaseEnabled ? (
            <form className="mt-8 space-y-3 border-t border-[#e3dcdc] pt-6" onSubmit={(e) => { e.preventDefault(); run(() => emailLogin(email, pw), "password"); }}>
              <h3 className="flex items-center gap-2 font-bold text-brand-ink"><Lock size={16} /> Staff sign-in</h3>
              <input aria-label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Work email" className="w-full rounded-full border border-[#cfc6c6] bg-white px-5 py-3" />
              <input aria-label="Password" type="password" required value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Password" className="w-full rounded-full border border-[#cfc6c6] bg-white px-5 py-3" />
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={!!busy} chevron>Sign in</Button>
                <Button variant="secondary" disabled={!!busy} onClick={() => run(googleLogin, "google")}>Continue with Google</Button>
              </div>
            </form>
          ) : (
            <p className="mt-8 border-t border-[#e3dcdc] pt-6 text-sm text-[#6b6b6b]"><Lock size={14} className="mr-1 inline" />Staff email and Google sign-in appear here once Firebase Authentication is configured.</p>
          )}
          <div className="mt-4"><ErrorBox error={err} /></div>
          <p className="mt-6 text-sm"><Link to="/articles" className="font-bold text-brand-plum hover:underline">New here? Read how RaktSetu works</Link></p>
        </div>
      </section>
    </div>
  );
}

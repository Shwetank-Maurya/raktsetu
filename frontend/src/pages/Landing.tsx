import { Link } from "react-router-dom";
import {
  ArrowRight, BarChart3, Bot, Building2, Check, Hospital, Map as MapIcon, ShieldCheck, Timer, Truck, Users,
} from "lucide-react";
import { SevBadge, SOFT } from "../components/ui";
import { ARTICLES, fmtDate } from "../content/articles";
import { describeNetwork, usePublicSummary, type PublicSummary } from "../lib/summary";

const FEATURES = [
  { icon: Timer, title: "Time-to-stockout", text: "Probability of running out in 24, 48 and 72 hours for every facility, group and component." },
  { icon: Truck, title: "Coordinated transfers", text: "An optimizer matches surplus to shortage under clinical constraints. A person approves every move." },
  { icon: BarChart3, title: "Expiry-aware stock", text: "Every unit tracked by expiry date, so blood about to expire on one shelf reaches a patient elsewhere." },
  { icon: MapIcon, title: "Network map", text: "One live view of risk across hospitals and blood banks, with transfer routes and travel times." },
  { icon: Bot, title: "Grounded assistant", text: "Ask in English or Hindi. Answers come only from live data and every number is checked." },
  { icon: ShieldCheck, title: "Safe by design", text: "Role-based access, an audit trail for every decision, and clinician sign-off for substitutions." },
];
const STEPS = [
  { t: "Record", d: "Stock changes go into an append-only ledger. Retries never double-count." },
  { t: "Forecast", d: "Demand is forecast with uncertainty: weekdays, festivals, dengue season, scheduled transfusions." },
  { t: "Simulate", d: "Thousands of possible futures per series give the probability and time of a stockout." },
  { t: "Act", d: "Transfers are proposed with reasons. A coordinator approves and both sides update live." },
];
const ROLES = [
  { icon: Hospital, title: "Hospitals", points: ["Your own countdown per blood group", "Compatible units nearby, ranked by travel time", "Receive transfers in one click"] },
  { icon: Building2, title: "Blood banks", points: ["Units that will expire unused, and where they are needed", "Dispatch approved transfers", "Targeted donor appeals"] },
  { icon: Users, title: "Coordinators", points: ["Risk across the whole region", "Approve optimizer proposals", "Mass-casualty stress tests"] },
];
const TECH = ["Gemini", "Firebase", "Google Maps", "OR-Tools", "Cloud Run", "BigQuery", "Neon Postgres"];
const SEV = ["critical", "high", "medium", "low"] as const;

function Preview({ d }: { d?: PublicSummary }) {
  const counts = d?.severity_counts ?? {};
  const total = SEV.reduce((a, s) => a + (counts[s] ?? 0), 0);
  const time = d?.last_cycle ? new Date(d.last_cycle).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" }) : null;
  return (
    <div className="rounded-2xl border border-line bg-white shadow-[0_24px_48px_-24px_rgba(24,24,27,0.18)]">
      <div className="flex items-center justify-between border-b border-line-soft px-4 py-3">
        <div className="flex gap-1.5">{["#e4e4e7", "#e4e4e7", "#e4e4e7"].map((c, i) => <span key={i} className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />)}</div>
        <span className="text-xs text-muted">Network risk{d?.network.region ? ` · ${d.network.region}` : ""}</span>
        <span className="flex items-center gap-1 text-xs text-success"><span className="h-1.5 w-1.5 rounded-full bg-success" />Live</span>
      </div>
      <div className="p-5">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-xs text-muted">Series monitored</div>
            <div className="stat-value text-3xl font-semibold tracking-tight text-ink">{d?.series_monitored ?? "—"}</div>
          </div>
          {time && <div className="text-xs text-faint">Updated {time} IST</div>}
        </div>
        <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-subtle">
          {total > 0 && SEV.map((s) => <div key={s} style={{ width: `${Math.max(((counts[s] ?? 0) / total) * 100, counts[s] ? 1.5 : 0)}%`, background: SOFT[s].dot }} />)}
        </div>
        <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2.5">
          {SEV.map((s) => (
            <li key={s} className="flex items-center justify-between text-sm"><SevBadge sev={s} /><span className="tnum text-ink">{counts[s] ?? 0}</span></li>
          ))}
        </ul>
        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-line-soft pt-4">
          <div className="rounded-lg bg-canvas p-3">
            <div className="text-xs text-muted">Forecast error vs baseline</div>
            <div className="mt-0.5 text-lg font-semibold text-ink">{d?.forecast?.wape_improvement_pct != null ? `−${d.forecast.wape_improvement_pct}%` : "—"}</div>
          </div>
          <div className="rounded-lg bg-canvas p-3">
            <div className="text-xs text-muted">80% interval coverage</div>
            <div className="mt-0.5 text-lg font-semibold text-ink">{d?.forecast?.coverage80 != null ? `${(d.forecast.coverage80 * 100).toFixed(1)}%` : "—"}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  const { data: d } = usePublicSummary();
  const network = describeNetwork(d);
  const alertsX = d?.replay ? Math.round(d.replay.alerts_a / Math.max(1, d.replay.alerts_b)) : null;
  const results = d?.replay ? [
    { label: "Expired units", value: d.replay.wastage_reduction_pct, text: `−${Math.round(d.replay.wastage_reduction_pct)}%` },
    { label: "Unmet demand", value: d.replay.unmet_reduction_pct, text: `−${Math.round(d.replay.unmet_reduction_pct)}%` },
    { label: "Days with a stockout", value: d.replay.stockout_days_reduction_pct, text: `−${Math.round(d.replay.stockout_days_reduction_pct)}%` },
  ] : [];

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_80%_20%,var(--color-accent-soft),transparent_70%)]" aria-hidden />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-6 pb-20 pt-16 lg:grid-cols-[1.1fr_1fr] lg:pt-24">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1 text-xs text-body">
              <span className="h-1.5 w-1.5 rounded-full bg-success" /> Live on {d?.facilities ?? "—"} facilities{d?.network.region ? ` in ${d.network.region}` : ""}
            </span>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.08] tracking-[-0.03em] text-ink sm:text-5xl lg:text-[3.5rem]">
              See blood shortages before they become emergencies.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
              RaktSetu forecasts demand, simulates time-to-stockout and coordinates transfers between hospitals and blood banks.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/signup" className="inline-flex h-11 items-center gap-2 rounded-lg bg-ink px-5 text-sm font-medium text-white hover:bg-black">Create account <ArrowRight size={16} /></Link>
              <Link to="/login" className="inline-flex h-11 items-center rounded-lg border border-line bg-white px-5 text-sm font-medium text-ink hover:bg-subtle">Sign in</Link>
              <Link to="/login" className="text-sm text-muted hover:text-ink">or try a demo account →</Link>
            </div>
          </div>
          <Preview d={d} />
        </div>
      </section>

      {/* Built with */}
      <section className="border-y border-line-soft">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-6 py-6">
          <span className="text-xs text-faint">Built with</span>
          {TECH.map((t) => <span key={t} className="text-sm font-medium text-muted">{t}</span>)}
        </div>
      </section>

      {/* Live numbers */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line lg:grid-cols-4">
          {[
            ["Facilities connected", d?.facilities],
            ["Series monitored", d?.series_monitored],
            ["Critical right now", d ? d.severity_counts.critical ?? 0 : undefined],
            ["Fewer alerts than fixed thresholds", alertsX ? `${alertsX}×` : undefined],
          ].map(([k, v]) => (
            <div key={String(k)} className="bg-white p-6">
              <div className="stat-value text-3xl font-semibold tracking-tight text-ink">{v ?? <span className="text-faint">—</span>}</div>
              <div className="mt-1 text-sm text-muted">{k}</div>
            </div>
          ))}
        </div>
        {network && <p className="mt-3 text-xs text-faint">Synthetic demo network: {network}.</p>}
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <p className="text-sm font-medium text-accent">Capabilities</p>
        <h2 className="mt-2 max-w-xl text-3xl font-semibold tracking-tight text-ink">Everything a blood network needs to act early</h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-xl border border-line bg-white p-6 transition-colors hover:border-ink/20">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-accent-soft text-accent"><f.icon size={18} /></span>
              <h3 className="mt-4 text-base font-semibold text-ink">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-line-soft bg-canvas">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <p className="text-sm font-medium text-accent">How it works</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-ink">From a stock entry to an approved transfer</h2>
          <ol className="mt-10 grid gap-6 md:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.t} className="relative">
                <div className="flex items-center gap-3">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink text-sm font-semibold text-white">{i + 1}</span>
                  {i < STEPS.length - 1 && <span className="hidden h-px flex-1 bg-line md:block" />}
                </div>
                <h3 className="mt-4 text-base font-semibold text-ink">{s.t}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Results */}
      {results.length > 0 && (
        <section className="mx-auto grid max-w-6xl gap-10 px-6 py-20 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <p className="text-sm font-medium text-accent">Measured, not claimed</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-ink">{d?.replay?.days}-day replay against fixed-threshold alerts</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted">Same demand, same donations, same starting stock. Only the policy changes. Figures come from the synthetic network and are reproducible.</p>
          </div>
          <div className="space-y-5 rounded-xl border border-line bg-white p-6">
            {results.map((r) => (
              <div key={r.label}>
                <div className="flex items-baseline justify-between"><span className="text-sm text-body">{r.label}</span><span className="text-xl font-semibold text-success">{r.text}</span></div>
                <div className="mt-2 grid grid-cols-[72px_1fr] items-center gap-3 text-xs text-muted">
                  <span>Fixed rule</span><div className="h-2 rounded-full bg-[#d4d4d8]" />
                  <span>RaktSetu</span><div className="h-2 rounded-full bg-success" style={{ width: `${100 - r.value}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Roles */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <p className="text-sm font-medium text-accent">Who it is for</p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {ROLES.map((r) => (
            <div key={r.title} className="rounded-xl border border-line bg-white p-6">
              <r.icon size={20} className="text-ink" />
              <h3 className="mt-4 text-base font-semibold text-ink">{r.title}</h3>
              <ul className="mt-3 space-y-2">
                {r.points.map((p) => <li key={p} className="flex gap-2 text-sm text-muted"><Check size={15} className="mt-0.5 shrink-0 text-success" />{p}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Articles */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="flex items-end justify-between border-b border-line-soft pb-4">
          <h2 className="text-base font-semibold text-ink">Articles</h2>
          <Link to="/articles" className="text-sm text-muted hover:text-ink">View all</Link>
        </div>
        <ul className="divide-y divide-line-soft">
          {ARTICLES.slice(0, 4).map((a) => (
            <li key={a.slug}>
              <Link to={`/articles/${a.slug}`} className="group flex flex-wrap items-baseline justify-between gap-2 py-5">
                <span className="text-[15px] text-ink group-hover:text-accent">{a.title} {a.accent}</span>
                <span className="text-xs text-faint">{fmtDate(a.date)} · {a.readMins} min</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="flex flex-wrap items-center justify-between gap-6 rounded-2xl bg-ink px-8 py-10 text-white">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight !text-white">Work at a hospital or blood bank?</h2>
            <p className="mt-1 text-sm text-white/70">Create an account and request access to your facility. Your coordinator approves it.</p>
          </div>
          <div className="flex gap-3">
            <Link to="/signup" className="inline-flex h-11 items-center gap-2 rounded-lg bg-white px-5 text-sm font-medium text-ink hover:bg-subtle">Create account <ArrowRight size={16} /></Link>
            <Link to="/login" className="inline-flex h-11 items-center rounded-lg border border-white/30 px-5 text-sm font-medium text-white hover:bg-white/10">Sign in</Link>
          </div>
        </div>
      </section>
    </div>
  );
}

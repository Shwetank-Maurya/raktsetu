import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Activity, BarChart3, Bot, Building2, ChevronRight, FlaskConical, Hospital, Pause, Play, ShieldCheck, Timer, Truck, Users } from "lucide-react";
import { api } from "../api/client";
import Art from "../components/Art";
import { ArticleCard } from "./Articles";
import { ARTICLES } from "../content/articles";

const SLIDES = [
  { title: "Predict blood shortages", accent: "before they become emergencies", body: "A probabilistic time-to-stockout for every hospital, blood group and component, judged against how fast help can arrive.",
    cta: ["Explore the live demo", "/login"], cta2: ["How it works", "/articles/time-to-stockout-probabilities-not-averages"], art: "countdown" as const,
    bg: "from-brand-sky via-[#1556c4] to-brand-blue", palette: ["#0b3fa8", "#3b8fe0"] as [string, string] },
  { title: "Every unit counts.", accent: "Use it or move it", body: "Units tracked by expiry date, so blood that would expire on one shelf is moved to a patient who needs it on another.",
    cta: ["Read the explainer", "/articles/use-it-or-move-it"], cta2: ["Try the demo", "/login"], art: "transfer" as const,
    bg: "from-[#7a1a55] via-brand-plum to-[#b0306f]", palette: ["#9b1218", "#d8343a"] as [string, string] },
  { title: "One city, one network.", accent: "Coordinated, then human-approved", body: "Google OR-Tools matches surplus to shortage under real clinical constraints. A coordinator reads the reasons and decides.",
    cta: ["Inside the optimizer", "/articles/how-the-optimizer-decides"], cta2: ["Sign in", "/login"], art: "network" as const,
    bg: "from-[#8f0c10] via-brand-crimson to-[#e3202a]", palette: ["#681861", "#a64d9b"] as [string, string] },
];

const ROLES = [
  { icon: Building2, title: "Blood banks", role: "bank", line: "Expiry warnings and donor appeals",
    text: "See which units will expire unused, where they are needed, and draft targeted donor appeals in Hindi or English." },
  { icon: Hospital, title: "Hospitals", role: "hospital", line: "Live availability within minutes",
    text: "Know your own countdown, find compatible units nearby ranked by travel time and shelf life, and receive transfers." },
  { icon: Users, title: "Regional coordinators", role: "coordinator", line: "One radar for the whole region",
    text: "A risk map, an optimizer and an approval desk, plus a mass-casualty stress test for preparedness planning." },
];

const STEPS = [
  { n: "01", t: "Record", d: "Every unit received, issued or discarded is appended to an idempotent ledger. Retries never double-count." },
  { n: "02", t: "Forecast", d: "A global model forecasts demand with uncertainty: weekdays, festivals, dengue season and thalassemia schedules." },
  { n: "03", t: "Simulate", d: "2,000 possible futures per series, consumed first-expiry-first-out, give the probability and time of a stockout." },
  { n: "04", t: "Act", d: "The optimizer proposes transfers with reasons. A human approves, both inventories update, everyone sees it live." },
];

const TILES = [
  { label: "Time-to-stockout", icon: Timer, to: "/articles/time-to-stockout-probabilities-not-averages", p: ["#0b3fa8", "#3b8fe0"] },
  { label: "Use it or move it", icon: Activity, to: "/articles/use-it-or-move-it", p: ["#9b1218", "#d8343a"] },
  { label: "Transfer optimizer", icon: Truck, to: "/articles/how-the-optimizer-decides", p: ["#7a1a55", "#b0306f"] },
  { label: "Mass-casualty stress test", icon: FlaskConical, to: "/articles/stress-testing-a-citys-blood-supply", p: ["#a41e6e", "#e3202a"] },
  { label: "Grounded Gemini copilot", icon: Bot, to: "/articles/grounded-ai-copilot", p: ["#353535", "#6a6a6a"] },
  { label: "Forecasts you can check", icon: BarChart3, to: "/articles/dengue-season-platelet-surge", p: ["#8a3b12", "#d17a3c"] },
];

function useHashScroll() {
  const { hash, pathname } = useLocation();
  useEffect(() => {
    if (!hash) { window.scrollTo(0, 0); return; }
    const el = document.getElementById(hash.slice(1));
    if (el) setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }, [hash, pathname]);
}

function Hero() {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => setI((x) => (x + 1) % SLIDES.length), 7000);
    return () => clearInterval(id);
  }, [paused]);
  const s = SLIDES[i];
  return (
    <section aria-roledescription="carousel" aria-label="Highlights" className={clsx("relative overflow-hidden bg-linear-to-br text-white transition-colors duration-700", s.bg)}>
      <div className="mx-auto grid min-h-[520px] max-w-[1440px] lg:grid-cols-2">
        <div className="relative z-10 flex flex-col justify-center px-4 py-16 lg:px-8" aria-live="polite">
          <h1 key={i} className="!text-white">
            <span className="block text-5xl font-bold leading-[1.0] tracking-[-0.05em] lg:text-[4.1rem]">{s.title}</span>
            <span className="mt-1 block font-serif text-4xl font-light leading-tight lg:text-[3.6rem]">{s.accent}</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-white/90">{s.body}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to={s.cta[1]} className="inline-flex items-center gap-1 rounded-full bg-white px-7 py-3.5 font-bold text-brand-ink hover:bg-brand-pink">{s.cta[0]} <ChevronRight size={18} strokeWidth={3} /></Link>
            <Link to={s.cta2[1]} className="inline-flex items-center gap-1 rounded-full border border-white px-7 py-3.5 font-bold hover:bg-white/10">{s.cta2[0]} <ChevronRight size={18} strokeWidth={3} /></Link>
          </div>
          <div className="mt-12 flex items-center gap-3">
            {SLIDES.map((_, k) => (
              <button key={k} onClick={() => setI(k)} aria-label={`Show slide ${k + 1}`} aria-current={k === i}
                className={clsx("h-6 w-6 rounded-full transition", k === i ? "bg-white" : "bg-white/40 hover:bg-white/70")} />
            ))}
            <button onClick={() => setPaused((p) => !p)} aria-label={paused ? "Play slideshow" : "Pause slideshow"} className="ml-2 grid h-8 w-8 place-items-center rounded-full border border-white/60 hover:bg-white/10">
              {paused ? <Play size={14} /> : <Pause size={14} />}
            </button>
          </div>
        </div>
        <div className="hero-angle relative hidden lg:block">
          <Art key={i} kind={s.art} palette={s.palette} className="absolute inset-0" />
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  useHashScroll();
  const sum = useQuery({ queryKey: ["public-summary"], queryFn: () => api.get("/api/public/summary"), staleTime: 60_000 });
  const d = sum.data;
  const alerts = d?.replay ? Math.round(d.replay.alerts_a / Math.max(1, d.replay.alerts_b)) : null;
  return (
    <div>
      <Hero />

      {/* Live snapshot */}
      <section className="mx-auto max-w-[1440px] px-4 py-10 lg:px-8" aria-label="Live network snapshot">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          {[
            ["Facilities connected", d?.facilities ?? "-"],
            ["Series monitored", d?.series_monitored ?? "-"],
            ["Critical right now", d?.severity_counts?.critical ?? 0],
            ["High risk right now", d?.severity_counts?.high ?? 0],
            ["Last network cycle", d?.last_cycle ? new Date(d.last_cycle).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" }) + " IST" : "-"],
          ].map(([k, v], idx) => (
            <div key={String(k)} className={clsx("rounded-br-[1.75rem] p-5", idx === 2 ? "bg-brand-pink" : "bg-brand-panel")}>
              <div className="text-xs font-bold uppercase tracking-wider text-[#6b6b6b]">{k}</div>
              <div className={clsx("mt-1 text-3xl font-bold tracking-tight", idx === 2 ? "text-[#B34700]" : "text-brand-ink")}>{String(v)}</div>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-[#6b6b6b]">Live from the synthetic demo network (31 facilities in Delhi NCT, refreshed every hour).</p>
      </section>

      {/* Roles (like the three location cards) */}
      <section id="roles" className="mx-auto max-w-[1440px] scroll-mt-40 px-4 pb-16 lg:px-8">
        <div className="grid gap-4 md:grid-cols-3">
          {ROLES.map((r) => (
            <div key={r.title} className="flex flex-col items-center rounded-br-[2.5rem] bg-brand-panel px-8 py-10 text-center">
              <span className="grid h-20 w-20 place-items-center rounded-full bg-linear-to-br from-brand-crimson to-brand-plum text-white shadow-md"><r.icon size={36} /></span>
              <h2 className="mt-5 text-3xl font-bold tracking-[-0.04em] text-black">{r.title}</h2>
              <p className="mt-3 text-[15px]">{r.text}</p>
              <div className="my-5 h-px w-full bg-[#d9d4d4]" />
              <p className="font-bold text-brand-plum">{r.line}</p>
              <Link to={`/login?role=${r.role}`} className="mt-6 inline-flex items-center gap-1 rounded-full bg-brand-plum px-7 py-3 font-bold text-white hover:bg-brand-plum-dark">
                Try as {r.title.toLowerCase().replace(/s$/, "")} <ChevronRight size={18} strokeWidth={3} />
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Split: network */}
      <section id="network" className="scroll-mt-40">
        <div className="mx-auto grid max-w-[1440px] items-center gap-10 lg:grid-cols-2">
          <Art kind="network" palette={["#7a1a55", "#b0306f"]} className="h-[380px] rounded-tr-[3rem] lg:h-[460px]" />
          <div className="px-4 py-6 lg:px-8">
            <h2 className="text-5xl font-bold leading-none tracking-[-0.05em] text-black">Our network</h2>
            <p className="font-serif text-5xl font-light text-brand-ink">across Delhi NCT</p>
            <p className="mt-6 text-lg">Eight large hospitals, thirteen smaller ones, two trauma centres, two maternity hospitals and six blood banks across four districts, all modelled at the level of the individual unit. One hospital runs out of O-negative while another discards expired units the same week. RaktSetu is the bridge between them.</p>
            <ul className="mt-6 grid gap-2 text-[15px] sm:grid-cols-2">
              {["8 blood groups x 4 components per facility", "Red cells, platelets, plasma and cryo", "Traffic-aware travel times and cold-chain limits", "Real-time updates for every browser"].map((x) => (
                <li key={x} className="flex gap-2"><ChevronRight className="mt-0.5 shrink-0 text-brand-plum" size={18} strokeWidth={3} />{x}</li>
              ))}
            </ul>
            <Link to="/login?role=coordinator" className="mt-8 inline-flex items-center gap-1 rounded-full bg-brand-crimson px-7 py-3 font-bold text-white hover:bg-[#8f0c10]">Open the risk map <ChevronRight size={18} strokeWidth={3} /></Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-[1440px] scroll-mt-40 px-4 py-20 lg:px-8">
        <h2 className="text-5xl font-bold leading-none tracking-[-0.05em] text-brand-plum-dark">How it works</h2>
        <p className="font-serif text-5xl font-light text-brand-plum-dark"><i>in</i> four steps</p>
        <ol className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.n} className="border-t-4 border-brand-plum pt-5">
              <div className="font-serif text-5xl font-light text-brand-plum">{s.n}</div>
              <h3 className="mt-2 text-2xl font-bold tracking-tight text-black">{s.t}</h3>
              <p className="mt-2 text-[15px]">{s.d}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Capability tiles (like the service tiles) */}
      <section id="capabilities" className="scroll-mt-40 bg-brand-pink py-20">
        <div className="mx-auto max-w-[1440px] px-4 lg:px-8">
          <h2 className="text-5xl font-bold leading-none tracking-[-0.05em] text-brand-plum-dark">What RaktSetu does</h2>
          <p className="font-serif text-5xl font-light text-brand-plum-dark"><i>for</i> every unit</p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {TILES.map((t) => (
              <Link key={t.label} to={t.to} className="group relative flex h-52 items-end overflow-hidden rounded-tr-[3rem] p-7 text-white" style={{ background: `linear-gradient(135deg, ${t.p[0]}, ${t.p[1]})` }}>
                <t.icon size={130} strokeWidth={1} className="absolute -right-4 -top-4 text-white/20 transition-transform duration-500 group-hover:scale-110" aria-hidden />
                <span className="relative flex items-center gap-1 text-2xl font-bold tracking-tight">{t.label} <ChevronRight size={24} strokeWidth={3} className="transition-transform group-hover:translate-x-1" /></span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Proof */}
      <section id="proof" className="mx-auto max-w-[1440px] scroll-mt-40 px-4 py-20 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h2 className="text-5xl font-bold leading-none tracking-[-0.05em] text-black">Measured,</h2>
            <p className="font-serif text-5xl font-light text-brand-ink"><i>not</i> claimed</p>
          </div>
          <p className="max-w-xl text-[15px]">A 90-day replay with identical demand for both policies: a static "alert at N units" rule versus RaktSetu. Synthetic data, reproducible by anyone, limits published alongside the wins.</p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            [d?.replay ? `-${d.replay.wastage_reduction_pct}%` : "-", "expired units", "use it or move it in action"],
            [d?.replay ? `-${d.replay.unmet_reduction_pct}%` : "-", "unmet demand", "fewer patients left waiting"],
            [alerts ? `${alerts}x` : "-", "fewer alerts", "signal, not noise"],
            [d?.forecast ? `${Math.round(d.forecast.coverage80 * 1000) / 10}%` : "-", "interval coverage", "80% bands that really cover 80%"],
          ].map(([v, k, s]) => (
            <div key={k} className="rounded-br-[2rem] border-l-4 border-brand-plum bg-brand-blush p-6">
              <div className="text-5xl font-bold tracking-[-0.05em] text-brand-plum">{v}</div>
              <div className="mt-1 text-lg font-bold text-brand-ink">{k}</div>
              <div className="text-sm">{s}</div>
            </div>
          ))}
        </div>
      </section>

      {/* News & articles */}
      <section className="bg-brand-pink py-20">
        <div className="mx-auto max-w-[1440px] px-4 lg:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-5xl font-bold leading-none tracking-[-0.05em] text-brand-plum-dark">News & articles</h2>
              <p className="font-serif text-5xl font-light text-brand-plum-dark"><i>from</i> RaktSetu</p>
            </div>
            <Link to="/articles" className="inline-flex items-center gap-1 rounded-full bg-brand-crimson px-7 py-3 font-bold text-white hover:bg-[#8f0c10]">Read all articles <ChevronRight size={18} strokeWidth={3} /></Link>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {ARTICLES.slice(0, 3).map((a) => <ArticleCard key={a.slug} a={a} />)}
          </div>
        </div>
      </section>

      {/* Responsible AI */}
      <section id="responsible" className="mx-auto max-w-[1440px] scroll-mt-40 px-4 py-20 lg:px-8">
        <h2 className="text-5xl font-bold leading-none tracking-[-0.05em] text-black">Responsible by design</h2>
        <p className="font-serif text-5xl font-light text-brand-ink">humans <i>decide</i></p>
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            ["Decision support, not a device", "Every transfer needs a human approval. Substitutions need a clinician's sign-off, every time."],
            ["Numbers from data, never from AI", "Gemini explains and converses. Every number it says is checked against the source data."],
            ["Privacy first", "No patient records. Donors are consent-based, with hashed phone numbers and first names only."],
            ["Honest about limits", "Synthetic data, published metrics and a 46-item edge-case table with tests and known gaps."],
          ].map(([t, x]) => (
            <div key={t} className="rounded-br-[2rem] bg-brand-panel p-6">
              <ShieldCheck className="text-brand-plum" size={30} />
              <h3 className="mt-3 text-xl font-bold tracking-tight text-black">{t}</h3>
              <p className="mt-2 text-[15px]">{x}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

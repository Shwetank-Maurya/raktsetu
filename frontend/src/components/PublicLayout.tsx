// Public (signed-out) site chrome: announcement bar, two-row sticky header, CTA band, footer.
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import clsx from "clsx";
import { ChevronRight, Menu, Phone, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { Logo } from "./Layout";

const MAIN = [
  { to: "/#network", label: "Our network" },
  { to: "/#how", label: "How it works" },
  { to: "/#capabilities", label: "What it does" },
  { to: "/articles", label: "News & articles" },
  { to: "/#responsible", label: "Responsible AI" },
];
const UTILITY = [
  { to: "/#roles", label: "For blood banks" },
  { to: "/#roles", label: "For hospitals" },
  { to: "/#proof", label: "Results" },
  { to: "/articles/how-the-optimizer-decides", label: "About" },
];

export default function PublicLayout() {
  const { lang, setLang } = useI18n();
  const loc = useLocation();
  const [banner, setBanner] = useState(() => sessionStorage.getItem("raktsetu.pbanner") !== "closed");
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col bg-white text-brand-body">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[1001] focus:bg-white focus:p-2">Skip to main content</a>
      {banner && (
        <div className="bg-brand-plum text-white">
          <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-4 py-3 text-sm lg:px-8">
            <p><b>Welcome to RaktSetu.</b> A hackathon prototype running on a fully synthetic Delhi network - explore it with a demo role, no account needed.</p>
            <button onClick={() => { sessionStorage.setItem("raktsetu.pbanner", "closed"); setBanner(false); }} aria-label="Close notification"
              className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white text-brand-plum hover:bg-brand-pink"><X size={14} strokeWidth={3} /></button>
          </div>
        </div>
      )}
      <header className="sticky top-0 z-[999] bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-[1440px] px-4 lg:px-8">
          <div className="flex items-center justify-between gap-4 border-b border-[#ece7e7] py-4">
            <Logo />
            <div className="hidden items-center gap-6 text-[15px] font-semibold text-brand-ink lg:flex">
              {UTILITY.map((u) => <Link key={u.label} to={u.to} className="hover:text-brand-plum">{u.label}</Link>)}
              <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="hover:text-brand-plum">{lang === "en" ? "हिन्दी" : "English"}</button>
              <Link to="/login" className="rounded-full bg-brand-plum px-6 py-2.5 text-sm font-bold text-white hover:bg-brand-plum-dark">Sign in</Link>
              <Link to="/login?role=hospital" className="inline-flex items-center gap-1 rounded-full bg-brand-crimson px-6 py-2.5 text-sm font-bold text-white hover:bg-[#8f0c10]">Find blood now <ChevronRight size={16} strokeWidth={3} /></Link>
            </div>
            <button className="rounded-full p-2 text-brand-plum hover:bg-brand-pink lg:hidden" onClick={() => setOpen((o) => !o)} aria-label="Menu" aria-expanded={open}>{open ? <X /> : <Menu />}</button>
          </div>
          <nav aria-label="Main" className="hidden items-center justify-between py-4 lg:flex">
            <ul className="flex items-center gap-8">
              {MAIN.map((m) => (
                <li key={m.label}>
                  <NavLink to={m.to} className={() => clsx("text-[17px] font-semibold tracking-[-0.02em] text-brand-ink hover:text-brand-plum",
                    m.to === "/articles" && loc.pathname.startsWith("/articles") && "text-brand-plum underline decoration-[3px] underline-offset-[10px]")}>{m.label}</NavLink>
                </li>
              ))}
            </ul>
            <span className="text-sm text-[#6b6b6b]">Decision support for hospitals and blood banks</span>
          </nav>
        </div>
        {open && (
          <nav aria-label="Mobile" className="border-t border-[#ece7e7] bg-white px-4 pb-5 lg:hidden" onClick={() => setOpen(false)}>
            <ul className="grid gap-1 py-2">{[...MAIN, ...UTILITY].map((m) => <li key={m.label + m.to}><Link to={m.to} className="block px-2 py-2 text-lg font-semibold text-brand-ink">{m.label}</Link></li>)}</ul>
            <div className="flex gap-2"><Link to="/login" className="rounded-full bg-brand-plum px-5 py-2.5 font-bold text-white">Sign in</Link>
              <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="px-3 font-semibold">{lang === "en" ? "हिन्दी" : "English"}</button></div>
          </nav>
        )}
      </header>

      <main id="main" className="flex-1"><Outlet /></main>

      <footer className="bg-brand-blush">
        <div className="bg-linear-to-r from-brand-magenta via-[#c4173c] to-[#e3202a] text-white">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-end justify-between gap-6 px-4 py-14 lg:px-8">
            <div>
              <p className="text-4xl font-bold leading-none tracking-[-0.045em] lg:text-5xl">Run a blood bank or hospital?</p>
              <p className="mt-1 font-serif text-4xl font-light lg:text-5xl">Join <i>the</i> network</p>
              <p className="mt-6 text-white/90">See it working on a live synthetic network:</p>
              <div className="mt-3 flex flex-wrap gap-3">
                <Link to="/login" className="inline-flex items-center gap-1 rounded-full bg-white px-6 py-3 font-bold text-brand-ink hover:bg-brand-pink">Try the demo <ChevronRight size={18} strokeWidth={3} /></Link>
                <Link to="/articles" className="inline-flex items-center gap-1 rounded-full border border-white px-6 py-3 font-bold hover:bg-white/10">Read how it works <ChevronRight size={18} strokeWidth={3} /></Link>
              </div>
            </div>
            <p className="flex items-center gap-2 text-xl"><Phone size={20} /> In a medical emergency, call 112 / 108</p>
          </div>
        </div>
        <div className="mx-auto max-w-[1440px] px-4 py-10 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-6 border-b border-[#e3dcdc] pb-10">
            <p className="max-w-3xl text-[15px]">RaktSetu means "blood bridge". We acknowledge the voluntary donors whose gift makes every unit possible, and the blood bank and hospital staff who move it. Built to be inclusive: English and हिन्दी, colour-blind-safe and keyboard accessible.</p>
            <div className="flex gap-2 text-xs font-bold">
              {["English", "हिन्दी", "WCAG-minded", "DPDP-aligned"].map((b) => <span key={b} className="rounded-full bg-white px-3 py-1.5 text-brand-plum ring-1 ring-[#e3dcdc]">{b}</span>)}
            </div>
          </div>
          <div className="grid gap-8 py-10 text-[15px] sm:grid-cols-2 lg:grid-cols-4">
            <div><Logo /><p className="mt-4 text-sm">A shared early-warning radar for blood. Decision support only, not a medical device. Humans approve every transfer.</p></div>
            <div><h3 className="mb-3 font-bold text-brand-ink">Platform</h3><ul className="space-y-2">{MAIN.slice(0, 3).map((m) => <li key={m.label}><Link to={m.to} className="hover:text-brand-plum">{m.label}</Link></li>)}<li><Link to="/login" className="hover:text-brand-plum">Sign in</Link></li></ul></div>
            <div><h3 className="mb-3 font-bold text-brand-ink">Read</h3><ul className="space-y-2">
              <li><Link to="/articles" className="hover:text-brand-plum">News & articles</Link></li>
              <li><Link to="/articles/time-to-stockout-probabilities-not-averages" className="hover:text-brand-plum">Time-to-stockout explained</Link></li>
              <li><Link to="/articles/grounded-ai-copilot" className="hover:text-brand-plum">Grounded AI</Link></li>
              <li><Link to="/articles/use-it-or-move-it" className="hover:text-brand-plum">Use it or move it</Link></li></ul></div>
            <div><h3 className="mb-3 font-bold text-brand-ink">Built with Google</h3><p className="text-sm">Gemini · Firebase (Auth, Firestore, Hosting, Messaging) · Google Maps Platform · Calendar API · OR-Tools · Cloud Run · BigQuery</p></div>
          </div>
          <div className="border-t border-[#e3dcdc] pt-6 text-sm text-[#6b6b6b]">Synthetic demo data · Clinical rules must be confirmed against NACO / NBTC guidance · © 2026 RaktSetu hackathon project</div>
        </div>
      </footer>
    </div>
  );
}

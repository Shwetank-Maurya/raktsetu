// Public (signed-out) chrome: one thin header and a one-line footer. Nothing else.
import { Link, NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";
import { useI18n } from "../lib/i18n";
import { Logo } from "./Layout";

export default function PublicLayout() {
  const { lang, setLang } = useI18n();
  const link = ({ isActive }: { isActive: boolean }) => clsx("text-sm", isActive ? "text-ink" : "text-muted hover:text-ink");
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[1001] focus:bg-white focus:p-2">Skip to content</a>
      <header className="sticky top-0 z-50 border-b border-line-soft bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Logo />
          <nav className="flex items-center gap-6" aria-label="Main">
            <NavLink to="/articles" className={link}>Articles</NavLink>
            <button onClick={() => setLang(lang === "en" ? "hi" : "en")} className="text-sm text-muted hover:text-ink">{lang === "en" ? "हिन्दी" : "English"}</button>
            <NavLink to="/login" className={link}>Sign in</NavLink>
            <Link to="/signup" className="inline-flex h-9 items-center rounded-lg bg-ink px-4 text-sm font-medium text-white hover:bg-black">Create account</Link>
          </nav>
        </div>
      </header>
      <main id="main" className="flex-1"><Outlet /></main>
      <footer className="border-t border-line-soft">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-xs text-muted">
          <span>© 2026 RaktSetu · Decision support for blood networks · Synthetic demo data</span>
          <span>In a medical emergency, call 112</span>
        </div>
      </footer>
    </div>
  );
}

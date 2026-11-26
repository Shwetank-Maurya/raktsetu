import { useEffect, useState, type ReactNode } from "react";
import clsx from "clsx";
import { ChevronRight, X } from "lucide-react";
import { SEV, hrs, type Sev } from "../lib/format";

/** Panel with the signature single large rounded corner. tone: white (bordered) | grey | pink */
export function Card({ title, action, children, className, tone = "white" }: {
  title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; tone?: "white" | "grey" | "pink";
}) {
  return (
    <section className={clsx(
      "rounded-br-[2rem] p-5",
      tone === "white" && "border border-[#e7e2e2] bg-white",
      tone === "grey" && "bg-brand-panel",
      tone === "pink" && "bg-brand-pink",
      className,
    )}>
      {(title || action) && (
        <header className="mb-4 flex items-center justify-between gap-2">
          {title && <h2 className="text-lg font-bold tracking-tight text-brand-ink">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/** Section heading: bold sans line + light serif accent line. */
export function SectionTitle({ title, accent, className }: { title: ReactNode; accent?: ReactNode; className?: string }) {
  return (
    <h2 className={clsx("text-3xl font-bold leading-none tracking-[-0.045em] text-brand-plum-dark", className)}>
      {title}
      {accent && <span className="serif-accent mt-1 text-3xl text-brand-plum-dark">{accent}</span>}
    </h2>
  );
}

export function SevBadge({ sev, label }: { sev: string; label?: string }) {
  const s = SEV[(sev as Sev) in SEV ? (sev as Sev) : "info"];
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold", s.bg, s.text)}>
      <span aria-hidden>{s.shape}</span>
      {label ?? sev}
    </span>
  );
}

export function Freshness({ hours }: { hours: number | null | undefined }) {
  if (hours == null) return <span className="rounded-full bg-brand-panel px-2 py-0.5 text-xs text-brand-body">never</span>;
  const stale = hours > 12;
  return (
    <span
      title="Hours since this facility last reported stock"
      className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold", stale ? "bg-[#D55E00] text-white" : hours > 4 ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900")}
    >
      {stale ? `stale ${Math.round(hours)}h` : hours < 1 ? "live" : `${Math.round(hours)}h ago`}
    </span>
  );
}

/** Ticks down every second from tts hours measured at asOf. */
export function Countdown({ hours, asOf }: { hours: number | null; asOf?: string | null }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (hours == null) return <span className="font-mono">{hrs(null)}</span>;
  const end = (asOf ? new Date(asOf).getTime() : now) + hours * 3600_000;
  const left = Math.max(0, end - now) / 1000;
  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = Math.floor(left % 60);
  return (
    <span className="font-mono tabular-nums" aria-label={`${h} hours ${m} minutes`}>
      {String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}
    </span>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Sev }) {
  return (
    <div className="rounded-br-[1.5rem] bg-brand-panel p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-[#6b6b6b]">{label}</div>
      <div className="mt-1 text-3xl font-bold tracking-tight text-brand-ink" style={tone ? { color: SEV[tone].color } : undefined}>{value}</div>
      {hint && <div className="mt-1 text-xs text-brand-body">{hint}</div>}
    </div>
  );
}

type Variant = "primary" | "crimson" | "secondary" | "ghost" | "danger" | "white" | "outline-white";
export function Button({ children, onClick, variant = "primary", disabled, type = "button", className, title, chevron }: {
  children: ReactNode; onClick?: () => void; variant?: Variant; disabled?: boolean;
  type?: "button" | "submit"; className?: string; title?: string; chevron?: boolean;
}) {
  return (
    <button
      type={type} onClick={onClick} disabled={disabled} title={title}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-full px-4 py-2 text-sm font-bold transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-plum/30 disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-brand-plum text-white hover:bg-brand-plum-dark",
        variant === "crimson" && "bg-brand-crimson text-white hover:bg-[#8f0c10]",
        variant === "secondary" && "border-2 border-brand-plum bg-white text-brand-plum hover:bg-brand-pink",
        variant === "ghost" && "text-brand-body hover:bg-brand-panel",
        variant === "danger" && "bg-brand-ink text-white hover:bg-black",
        variant === "white" && "bg-white text-brand-ink hover:bg-brand-pink",
        variant === "outline-white" && "border border-white text-white hover:bg-white/10",
        className,
      )}
    >
      {children}
      {chevron && <ChevronRight size={16} strokeWidth={3} aria-hidden />}
    </button>
  );
}

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div role="status" className="flex items-center gap-2 p-4 text-sm text-brand-body">
    <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-plum border-t-transparent" /> {label}...
  </div>
);

export const ErrorBox = ({ error }: { error: unknown }) =>
  error ? <div role="alert" className="rounded-br-2xl border-l-4 border-brand-crimson bg-brand-pink p-3 text-sm text-brand-crimson">{(error as Error).message}</div> : null;

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1000] flex justify-end bg-black/40" onClick={onClose}>
      <aside role="dialog" aria-modal="true" className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-5 flex items-center justify-between border-b border-brand-pink pb-3">
          <h2 className="text-2xl font-bold tracking-tight text-brand-ink">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-brand-plum hover:bg-brand-pink"><X size={20} /></button>
        </div>
        {children}
      </aside>
    </div>
  );
}

export function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: (string | [string, string])[]; label: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold text-brand-body">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-full border border-[#cfc6c6] bg-white px-3 py-2 text-sm font-normal text-brand-ink focus:border-brand-plum">
        {options.map((o) => (Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o}>{o}</option>))}
      </select>
    </label>
  );
}

export const AsOf = ({ iso, light = false }: { iso?: string | null; light?: boolean }) =>
  iso ? <span className={clsx("text-xs", light ? "text-white/85" : "text-[#6b6b6b]")}>data as of {new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })} IST</span> : null;

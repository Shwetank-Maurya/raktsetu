import { useEffect, useState, type ReactNode } from "react";
import clsx from "clsx";
import { ChevronRight, Inbox, X, type LucideIcon } from "lucide-react";
import { hrs } from "../lib/format";
import { SOFT } from "../lib/styles";

/* ---------------------------------------------------------------- layout primitives */

export function PageHeader({ title, description, actions, eyebrow }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium text-muted">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p className="max-w-3xl">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, description, action, children, className, tone = "white", padded = true }: {
  title?: ReactNode; description?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
  tone?: "white" | "grey" | "pink"; padded?: boolean;
}) {
  return (
    <section className={clsx("rounded-xl border", tone === "white" && "border-line bg-white", tone === "grey" && "border-line bg-subtle/60",
      tone === "pink" && "border-accent-line bg-accent-soft", className)}>
      {(title || action) && (
        <header className={clsx("flex items-start justify-between gap-3", padded ? "px-5 pt-4" : "border-b border-line px-5 py-3")}>
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={clsx(padded && "p-5", padded && (title || action) && "pt-3")}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone, icon: Icon }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string; icon?: LucideIcon }) {
  const toneColor = tone ? SOFT[tone as keyof typeof SOFT]?.fg : undefined;
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted">{label}</span>
        {Icon && <Icon size={16} className="text-faint" aria-hidden />}
      </div>
      <div className="stat-value mt-2 text-2xl font-semibold tracking-tight text-ink" style={toneColor ? { color: toneColor } : undefined}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function EmptyState({ title, children, icon: Icon = Inbox }: { title: string; children?: ReactNode; icon?: LucideIcon }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-10 text-center">
      <Icon size={22} className="text-faint" aria-hidden />
      <div className="mt-2 text-sm font-medium text-ink">{title}</div>
      {children && <div className="mt-1 text-xs text-muted">{children}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- status */

export function SevBadge({ sev, label }: { sev: string; label?: string }) {
  const s = SOFT[(sev as keyof typeof SOFT) in SOFT ? (sev as keyof typeof SOFT) : "info"];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs font-medium capitalize" style={{ background: s.bg, color: s.fg }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.dot }} aria-hidden />
      {label ?? sev}
    </span>
  );
}

export function Freshness({ hours }: { hours: number | null | undefined }) {
  if (hours == null) return <span className="rounded-md bg-subtle px-1.5 py-0.5 text-xs text-muted">no data</span>;
  const stale = hours > 12;
  return (
    <span title="Time since this facility last reported stock"
      className={clsx("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium", stale ? "bg-[#fdeee6] text-[#a34000]" : "bg-subtle text-body")}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", stale ? "bg-[#D55E00]" : hours > 4 ? "bg-[#E69F00]" : "bg-success")} aria-hidden />
      {stale ? `stale ${Math.round(hours)}h` : hours < 1 ? "live" : `${Math.round(hours)}h ago`}
    </span>
  );
}

/** Ticks down every second from tts hours measured at asOf. */
export function Countdown({ hours, asOf }: { hours: number | null; asOf?: string | null }) {
  const [now, setNow] = useState(() => Date.now());
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

export function Bar({ value, color = "var(--color-accent)", className }: { value: number; color?: string; className?: string }) {
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-subtle", className)} role="meter" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.min(100, value * 100))}%`, background: color }} />
    </div>
  );
}

/* ---------------------------------------------------------------- controls */

type Variant = "primary" | "crimson" | "secondary" | "ghost" | "danger" | "white" | "outline-white";
export function Button({ children, onClick, variant = "primary", disabled, type = "button", className, title, chevron, size = "md" }: {
  children: ReactNode; onClick?: () => void; variant?: Variant; disabled?: boolean; size?: "sm" | "md";
  type?: "button" | "submit"; className?: string; title?: string; chevron?: boolean;
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "md" ? "h-9 px-3.5 text-sm" : "h-7 px-2.5 text-xs",
        (variant === "primary" || variant === "crimson") && "bg-accent text-white hover:bg-accent-strong",
        variant === "secondary" && "border border-line bg-white text-ink hover:bg-subtle",
        variant === "ghost" && "text-body hover:bg-subtle",
        variant === "danger" && "bg-ink text-white hover:bg-black",
        variant === "white" && "bg-white text-ink hover:bg-subtle",
        variant === "outline-white" && "border border-white/40 text-white hover:bg-white/10",
        className,
      )}>
      {children}
      {chevron && <ChevronRight size={15} aria-hidden />}
    </button>
  );
}

export function Tabs({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: [string, ReactNode][] }) {
  return (
    <div role="tablist" className="inline-flex rounded-lg border border-line bg-subtle/70 p-0.5">
      {options.map(([k, label]) => (
        <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}
          className={clsx("rounded-md px-3 py-1 text-sm font-medium transition-colors", value === k ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink")}>{label}</button>
      ))}
    </div>
  );
}

export function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: (string | [string, string])[]; label: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-muted">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-lg border border-line bg-white px-2.5 text-sm font-normal text-ink focus:border-accent focus:outline-none">
        {options.map((o) => (Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o}>{o}</option>))}
      </select>
    </label>
  );
}

/* ---------------------------------------------------------------- feedback */

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div role="status" className="flex items-center gap-2 p-4 text-sm text-muted">
    <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" /> {label}…
  </div>
);

export const Skeleton = ({ className }: { className?: string }) => <div className={clsx("animate-pulse rounded-lg bg-subtle", className)} />;

export const ErrorBox = ({ error }: { error: unknown }) =>
  error ? <div role="alert" className="rounded-lg border border-accent-line bg-accent-soft px-3 py-2 text-sm text-accent-strong">{(error as Error).message}</div> : null;

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1000] flex justify-end bg-ink/30 backdrop-blur-[1px]" onClick={onClose}>
      <aside role="dialog" aria-modal="true" className="h-full w-full max-w-lg overflow-y-auto border-l border-line bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 flex items-center justify-between border-b border-line bg-white px-5 py-3.5">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-muted hover:bg-subtle hover:text-ink"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </aside>
    </div>
  );
}

export const AsOf = ({ iso, light = false }: { iso?: string | null; light?: boolean }) =>
  iso ? <span className={clsx("text-xs", light ? "text-white/80" : "text-muted")}>Updated {new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })} IST</span> : null;

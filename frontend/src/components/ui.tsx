import { useEffect, useState, type ReactNode } from "react";
import clsx from "clsx";
import { X } from "lucide-react";
import { SEV, hrs, type Sev } from "../lib/format";

export function Card({ title, action, children, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={clsx("rounded-xl border border-slate-200 bg-white p-4 shadow-sm", className)}>
      {(title || action) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold text-slate-700">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function SevBadge({ sev, label }: { sev: string; label?: string }) {
  const s = SEV[(sev as Sev) in SEV ? (sev as Sev) : "info"];
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold", s.bg, s.text)}>
      <span aria-hidden>{s.shape}</span>
      {label ?? sev}
    </span>
  );
}

export function Freshness({ hours }: { hours: number | null | undefined }) {
  if (hours == null) return <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-600">never</span>;
  const stale = hours > 12;
  return (
    <span
      title="Hours since this facility last reported stock"
      className={clsx("rounded px-1.5 py-0.5 text-xs", stale ? "bg-[#D55E00] text-white" : hours > 4 ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900")}
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
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold" style={tone ? { color: SEV[tone].color } : undefined}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function Button({ children, onClick, variant = "primary", disabled, type = "button", className, title }: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "danger" | "secondary"; disabled?: boolean;
  type?: "button" | "submit"; className?: string; title?: string;
}) {
  return (
    <button
      type={type} onClick={onClick} disabled={disabled} title={title}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-rose-700 text-white hover:bg-rose-800",
        variant === "secondary" && "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
        variant === "ghost" && "text-slate-600 hover:bg-slate-100",
        variant === "danger" && "bg-slate-800 text-white hover:bg-slate-900",
        className,
      )}
    >
      {children}
    </button>
  );
}

export const Spinner = ({ label = "Loading" }: { label?: string }) => (
  <div role="status" className="flex items-center gap-2 p-4 text-sm text-slate-500">
    <span className="h-4 w-4 animate-spin rounded-full border-2 border-rose-700 border-t-transparent" /> {label}...
  </div>
);

export const ErrorBox = ({ error }: { error: unknown }) =>
  error ? <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{(error as Error).message}</div> : null;

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside role="dialog" aria-modal="true" className="h-full w-full max-w-lg overflow-y-auto bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-slate-100"><X size={18} /></button>
        </div>
        {children}
      </aside>
    </div>
  );
}

export function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: (string | [string, string])[]; label: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-600">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800">
        {options.map((o) => (Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o}>{o}</option>))}
      </select>
    </label>
  );
}

export const AsOf = ({ iso }: { iso?: string | null }) =>
  iso ? <span className="text-xs text-slate-500">data as of {new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })} IST</span> : null;

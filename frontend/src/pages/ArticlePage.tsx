import { useEffect } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { ARTICLES, bySlug, fmtDate } from "../content/articles";
import { useAuth } from "../lib/auth";
import { contentVars, fill, usePublicSummary } from "../lib/summary";

export default function ArticlePage() {
  const { slug = "" } = useParams();
  const { user } = useAuth();
  const a = bySlug(slug);
  const v = contentVars(usePublicSummary().data);
  useEffect(() => {
    window.scrollTo(0, 0);
    if (a) document.title = `${a.title} ${a.accent} · RaktSetu`;
    return () => { document.title = "RaktSetu - Predictive Blood Network"; };
  }, [a]);
  if (!a) return <Navigate to="/articles" replace />;
  const idx = ARTICLES.findIndex((x) => x.slug === a.slug);
  const next = ARTICLES[(idx + 1) % ARTICLES.length];
  return (
    <article className="mx-auto max-w-2xl px-6 py-14">
      <Link to="/articles" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft size={14} /> Articles</Link>
      <div className="mt-8 text-xs text-faint">{a.category} · {fmtDate(a.date)} · {a.readMins} min read</div>
      <h1 className="mt-2 text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-4xl">{a.title} {a.accent}</h1>
      <p className="mt-4 text-lg leading-relaxed text-muted">{a.excerpt}</p>
      <div className="mt-10 space-y-5 text-[16px] leading-[1.75] text-body">
        {a.body.map((b, i) => (
          <div key={i}>
            {b.h && <h2 className="mb-2 mt-8 text-lg font-semibold text-ink">{b.h}</h2>}
            {b.p && <p>{fill(b.p, v)}</p>}
            {b.list && <ul className="mt-2 list-disc space-y-1.5 pl-5 marker:text-faint">{b.list.map((l) => <li key={l}>{fill(l, v)}</li>)}</ul>}
            {b.quote && <blockquote className="my-6 border-l-2 border-accent pl-5 text-ink">{fill(b.quote, v)}</blockquote>}
          </div>
        ))}
      </div>
      <p className="mt-12 border-t border-line-soft pt-6 text-xs leading-relaxed text-faint">
        Results quoted here come from RaktSetu's synthetic demo network and are reproducible from the project repository. Clinical
        parameters follow common practice and must be confirmed against local guidance. RaktSetu is decision support, not a medical device.
      </p>
      <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
        <Link to={`/articles/${next.slug}`} className="text-sm text-ink hover:text-accent">Next: {next.title} {next.accent} →</Link>
        <Link to={user ? "/" : "/login"} className="inline-flex h-9 items-center rounded-lg bg-ink px-4 text-sm font-medium text-white hover:bg-black">{user ? "Back to dashboard" : "Try the demo"}</Link>
      </div>
    </article>
  );
}

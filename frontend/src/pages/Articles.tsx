import { useState } from "react";
import { Link } from "react-router-dom";
import { ARTICLES, fmtDate, type Article } from "../content/articles";

export function ArticleCard({ a }: { a: Article; large?: boolean }) {
  return (
    <Link to={`/articles/${a.slug}`} className="group block rounded-xl border border-line bg-white p-5 hover:border-ink/25">
      <div className="text-xs text-muted">{a.category} · {fmtDate(a.date)}</div>
      <h3 className="mt-2 text-[15px] font-semibold leading-snug text-ink group-hover:text-accent">{a.title} {a.accent}</h3>
      <p className="mt-2 line-clamp-3 text-sm text-muted">{a.excerpt}</p>
    </Link>
  );
}

const CATS = ["All", "Inside RaktSetu", "Explainer", "Field notes", "Responsible AI"] as const;

export default function Articles() {
  const [cat, setCat] = useState<(typeof CATS)[number]>("All");
  const list = ARTICLES.filter((a) => cat === "All" || a.category === cat);
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight text-ink">Articles</h1>
      <p className="mt-2 text-muted">How RaktSetu forecasts, optimises and keeps its AI honest.</p>
      <div className="mt-8 flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by category">
        {CATS.map((c) => (
          <button key={c} role="tab" aria-selected={cat === c} onClick={() => setCat(c)}
            className={cat === c ? "rounded-full bg-ink px-3 py-1 text-xs font-medium text-white" : "rounded-full px-3 py-1 text-xs font-medium text-muted hover:bg-subtle hover:text-ink"}>{c}</button>
        ))}
      </div>
      <ul className="mt-6 divide-y divide-line-soft border-t border-line-soft">
        {list.map((a) => (
          <li key={a.slug}>
            <Link to={`/articles/${a.slug}`} className="group block py-6">
              <div className="text-xs text-faint">{a.category} · {fmtDate(a.date)} · {a.readMins} min read</div>
              <h2 className="mt-1.5 text-lg font-semibold leading-snug text-ink group-hover:text-accent">{a.title} {a.accent}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{a.excerpt}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

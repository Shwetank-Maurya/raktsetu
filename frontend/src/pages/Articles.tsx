import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import Art from "../components/Art";
import { ARTICLES, fmtDate, type Article } from "../content/articles";

export function ArticleCard({ a, large = false }: { a: Article; large?: boolean }) {
  return (
    <article className="group flex flex-col">
      <Link to={`/articles/${a.slug}`} className="block" tabIndex={-1} aria-hidden>
        <Art kind={a.art} palette={a.palette} className={large ? "aspect-[16/9] rounded-tr-[3rem]" : "aspect-[3/2] rounded-tr-[2.5rem]"} />
      </Link>
      <div className="mt-4 flex items-center gap-3 text-sm">
        <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-brand-plum ring-1 ring-[#e3dcdc]">{a.category}</span>
        <time dateTime={a.date} className="text-[#6b6b6b]">{fmtDate(a.date)}</time>
        <span className="text-[#6b6b6b]">· {a.readMins} min read</span>
      </div>
      <h3 className={large ? "mt-3 text-3xl font-bold leading-tight tracking-[-0.04em] text-black" : "mt-3 text-2xl font-bold leading-tight tracking-[-0.035em] text-black"}>
        <Link to={`/articles/${a.slug}`} className="hover:text-brand-plum">{a.title} <span className="font-serif font-light">{a.accent}</span></Link>
      </h3>
      <p className="mt-2 flex-1 text-[15px]">{a.excerpt}</p>
      <Link to={`/articles/${a.slug}`} className="mt-4 inline-flex items-center gap-1 font-bold text-brand-plum">
        Read more <ChevronRight size={18} strokeWidth={3} className="transition-transform group-hover:translate-x-1" />
      </Link>
    </article>
  );
}

const CATS = ["All", "Inside RaktSetu", "Explainer", "Field notes", "Responsible AI"] as const;

export default function Articles() {
  const [cat, setCat] = useState<(typeof CATS)[number]>("All");
  const list = ARTICLES.filter((a) => cat === "All" || a.category === cat);
  const [lead, ...rest] = list;
  return (
    <div>
      <section className="bg-brand-pink">
        <div className="mx-auto max-w-[1440px] px-4 py-16 lg:px-8">
          <nav aria-label="Breadcrumb" className="text-sm"><Link to="/" className="text-brand-plum hover:underline">Home</Link> <span className="mx-1">/</span> News & articles</nav>
          <h1 className="mt-4 text-5xl font-bold leading-none tracking-[-0.05em] text-brand-plum-dark lg:text-6xl">News & articles</h1>
          <p className="font-serif text-5xl font-light text-brand-plum-dark lg:text-6xl"><i>from</i> RaktSetu</p>
          <p className="mt-6 max-w-2xl text-lg">Explainers on blood supply, field notes on seasonal demand, and a look inside how RaktSetu forecasts, optimises and keeps its AI honest.</p>
          <div className="mt-8 flex flex-wrap gap-2" role="tablist" aria-label="Filter by category">
            {CATS.map((c) => (
              <button key={c} role="tab" aria-selected={cat === c} onClick={() => setCat(c)}
                className={cat === c ? "rounded-full bg-brand-plum px-5 py-2 text-sm font-bold text-white" : "rounded-full bg-white px-5 py-2 text-sm font-bold text-brand-ink ring-1 ring-[#e3dcdc] hover:ring-brand-plum"}>{c}</button>
            ))}
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-[1440px] px-4 py-16 lg:px-8">
        {lead && (
          <div className="mb-14 grid gap-8 border-b border-[#ece7e7] pb-14 lg:grid-cols-2">
            <ArticleCard a={lead} large />
            <div className="flex flex-col justify-center rounded-br-[2.5rem] bg-brand-blush p-8">
              <div className="text-xs font-bold uppercase tracking-wider text-brand-plum">Featured</div>
              <p className="mt-3 font-serif text-3xl font-light leading-snug text-brand-ink">"{lead.body.find((b) => b.quote)?.quote ?? lead.excerpt}"</p>
              <Link to={`/articles/${lead.slug}`} className="mt-6 inline-flex w-fit items-center gap-1 rounded-full bg-brand-plum px-6 py-3 font-bold text-white hover:bg-brand-plum-dark">Read the article <ChevronRight size={18} strokeWidth={3} /></Link>
            </div>
          </div>
        )}
        <div className="grid gap-x-6 gap-y-12 md:grid-cols-2 lg:grid-cols-3">
          {rest.map((a) => <ArticleCard key={a.slug} a={a} />)}
        </div>
        {list.length === 0 && <p>No articles in this category yet.</p>}
      </section>
    </div>
  );
}

import { useEffect } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Art from "../components/Art";
import { ARTICLES, bySlug, fmtDate } from "../content/articles";
import { useAuth } from "../lib/auth";
import { ArticleCard } from "./Articles";

export default function ArticlePage() {
  const { slug = "" } = useParams();
  const { user } = useAuth();
  const a = bySlug(slug);
  useEffect(() => { window.scrollTo(0, 0); if (a) document.title = `${a.title} ${a.accent} - RaktSetu`; return () => { document.title = "RaktSetu - Predictive Blood Network"; }; }, [a]);
  if (!a) return <Navigate to="/articles" replace />;
  const more = ARTICLES.filter((x) => x.slug !== a.slug).slice(0, 3);
  return (
    <article>
      <header className="bg-brand-pink">
        <div className="mx-auto grid max-w-[1440px] items-center gap-10 px-4 py-14 lg:grid-cols-2 lg:px-8">
          <div>
            <nav aria-label="Breadcrumb" className="text-sm"><Link to="/" className="text-brand-plum hover:underline">Home</Link> <span className="mx-1">/</span> <Link to="/articles" className="text-brand-plum hover:underline">News & articles</Link></nav>
            <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
              <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-brand-plum ring-1 ring-[#e3dcdc]">{a.category}</span>
              <time dateTime={a.date}>{fmtDate(a.date)}</time><span>· {a.readMins} min read</span>
            </div>
            <h1 className="mt-4 !text-[2.6rem] lg:!text-[3.4rem]">{a.title}<span className="accent">{a.accent}</span></h1>
            <p className="mt-5 text-lg">{a.excerpt}</p>
          </div>
          <Art kind={a.art} palette={a.palette} className="aspect-[3/2] rounded-tr-[3rem]" />
        </div>
      </header>

      <div className="mx-auto grid max-w-[1440px] gap-12 px-4 py-14 lg:grid-cols-[minmax(0,1fr)_320px] lg:px-8">
        <div className="max-w-3xl text-[18px] leading-relaxed text-brand-body">
          {a.body.map((b, i) => (
            <div key={i} className="mb-6">
              {b.h && <h2 className="mb-2 mt-8 text-2xl font-bold tracking-tight text-black">{b.h}</h2>}
              {b.p && <p>{b.p}</p>}
              {b.list && <ul className="mt-3 space-y-2">{b.list.map((l) => <li key={l} className="flex gap-2"><ChevronRight className="mt-1 shrink-0 text-brand-plum" size={18} strokeWidth={3} />{l}</li>)}</ul>}
              {b.quote && <blockquote className="my-8 border-l-4 border-brand-plum pl-6 font-serif text-2xl font-light leading-snug text-brand-ink">{b.quote}</blockquote>}
            </div>
          ))}
          <div className="mt-10 rounded-br-[2rem] bg-brand-blush p-5 text-sm">
            Figures described as results come from RaktSetu's synthetic demo network and are reproducible from the project repository. Clinical parameters follow common transfusion practice and must be confirmed against local guidance. RaktSetu is decision support, not a medical device.
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/articles" className="inline-flex items-center gap-1 rounded-full border-2 border-brand-plum px-6 py-2.5 font-bold text-brand-plum hover:bg-brand-pink"><ChevronLeft size={18} strokeWidth={3} /> All articles</Link>
            <Link to={user ? "/" : "/login"} className="inline-flex items-center gap-1 rounded-full bg-brand-plum px-6 py-2.5 font-bold text-white hover:bg-brand-plum-dark">{user ? "Back to the dashboard" : "See it in the live demo"} <ChevronRight size={18} strokeWidth={3} /></Link>
          </div>
        </div>
        <aside className="space-y-6 lg:sticky lg:top-44 lg:self-start">
          <div className="rounded-br-[2rem] bg-linear-to-br from-brand-magenta to-[#e3202a] p-6 text-white">
            <p className="text-2xl font-bold leading-tight tracking-tight">See it working</p>
            <p className="font-serif text-2xl font-light">on a live network</p>
            <p className="mt-3 text-sm text-white/90">31 synthetic facilities, hourly forecasts and an optimizer you can approve yourself.</p>
            <Link to={user ? "/" : "/login"} className="mt-5 inline-flex items-center gap-1 rounded-full bg-white px-5 py-2.5 text-sm font-bold text-brand-ink">{user ? "Open dashboard" : "Try the demo"} <ChevronRight size={16} strokeWidth={3} /></Link>
          </div>
          <div className="rounded-br-[2rem] bg-brand-panel p-6">
            <h2 className="font-bold text-brand-ink">In this series</h2>
            <ul className="mt-3 space-y-3 text-[15px]">{ARTICLES.filter((x) => x.slug !== a.slug).slice(0, 5).map((x) => (
              <li key={x.slug}><Link to={`/articles/${x.slug}`} className="hover:text-brand-plum"><b className="text-brand-ink">{x.title}</b> {x.accent}</Link></li>))}
            </ul>
          </div>
        </aside>
      </div>

      <section className="bg-brand-pink py-16">
        <div className="mx-auto max-w-[1440px] px-4 lg:px-8">
          <h2 className="text-4xl font-bold leading-none tracking-[-0.05em] text-brand-plum-dark">Keep reading</h2>
          <p className="font-serif text-4xl font-light text-brand-plum-dark"><i>more</i> from RaktSetu</p>
          <div className="mt-8 grid gap-6 md:grid-cols-3">{more.map((x) => <ArticleCard key={x.slug} a={x} />)}</div>
        </div>
      </section>
    </article>
  );
}

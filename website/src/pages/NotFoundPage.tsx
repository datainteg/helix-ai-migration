import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Home, ArrowLeft } from "lucide-react";

/**
 * L-012: a real 404 page instead of a silent <Navigate to="/"> redirect.
 *
 * Redirecting unknown routes to "/" returned HTTP 200 for dead links, so
 * crawlers indexed them and analytics never recorded the miss. This renders a
 * dedicated not-found view. Static hosts (Netlify/Vercel/Caddy) can be wired to
 * serve this with a 404 status; the `<title>` + noindex hint below let crawlers
 * treat it as a soft-404 even on SPA hosting that always returns 200.
 */
export function NotFoundPage() {
  useEffect(() => {
    const prevTitle = document.title;
    document.title = "404 — Page not found · Helix";
    // Hint crawlers not to index this URL even though the SPA host returns 200.
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    return () => {
      document.title = prevTitle;
      document.head.removeChild(meta);
    };
  }, []);

  return (
    <section className="py-24 md:py-32 container-tight">
      <div className="max-w-xl">
        <div className="eyebrow mb-3">Error 404</div>
        <h1 className="text-4xl md:text-5xl font-semibold tracking-tight text-ink">
          Page not found
        </h1>
        <p className="mt-4 text-[14.5px] text-ink-3 leading-relaxed">
          The page you&rsquo;re looking for doesn&rsquo;t exist or may have been
          moved. Check the URL, or head back to a known page below.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 h-10 rounded-md bg-ink text-white text-[13.5px] font-medium hover:bg-zinc-800 focus-ring"
          >
            <Home className="h-4 w-4" />
            Back to home
          </Link>
          <Link
            to="/docs"
            className="inline-flex items-center gap-2 px-4 h-10 rounded-md bg-zinc-100 text-ink-2 text-[13.5px] font-medium hover:bg-zinc-200 focus-ring"
          >
            <ArrowLeft className="h-4 w-4" />
            Read the docs
          </Link>
        </div>
      </div>
    </section>
  );
}

import Link from "next/link";

/**
 * Route-level 404 page.
 * Next 14 renders this when no segment matches the URL, or when a server
 * component calls `notFound()`.
 */
export default function NotFound() {
  return (
    <div className="min-h-screen bg-app text-ink flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="eyebrow mb-3">404 · NOT FOUND</div>
      <h1 className="text-[32px] font-medium tracking-editorial leading-[1.1] m-0">
        Page not found
      </h1>
      <p className="mt-3 max-w-md text-[13px] text-ink-3">
        The page you requested doesn&apos;t exist, has moved, or is part of an
        admin surface that hasn&apos;t shipped yet.
      </p>
      <div className="mt-6 flex gap-2">
        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center h-8 px-3 text-[12.5px] rounded-[8px] border border-ink bg-ink text-white hover:bg-zinc-800"
        >
          Back to dashboard
        </Link>
        <Link
          href="/projects"
          className="inline-flex items-center justify-center h-8 px-3 text-[12.5px] rounded-[8px] border border-hx-2 bg-surface text-ink-2 hover:bg-app-2"
        >
          View projects
        </Link>
      </div>
    </div>
  );
}

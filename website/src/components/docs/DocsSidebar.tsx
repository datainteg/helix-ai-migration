import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";

import { DOC_CATEGORIES, DOCS, type DocEntry } from "@/data/docs-content";
import { DocsSearch } from "./DocsSearch";

interface DocsSidebarProps {
  /**
   * Tailwind class applied to the outer container. Allows DocsLayout to swap
   * between the sticky desktop column and the mobile `<details>` accordion
   * without forking the component.
   */
  className?: string;
  /**
   * When true the active NavLink stays highlighted; defaults to true. The
   * `<details>` accordion variant might want to disable hover ring for
   * accessibility.
   */
  showActive?: boolean;
}

function groupFiltered(query: string): Record<string, DocEntry[]> {
  const q = query.trim().toLowerCase();
  const grouped: Record<string, DocEntry[]> = {};
  for (const cat of DOC_CATEGORIES) grouped[cat] = [];
  for (const doc of DOCS) {
    if (q) {
      const haystack = `${doc.title}\n${doc.summary}`.toLowerCase();
      if (!haystack.includes(q)) continue;
    }
    if (!grouped[doc.category]) grouped[doc.category] = [];
    grouped[doc.category].push(doc);
  }
  return grouped;
}

export function DocsSidebar({ className, showActive = true }: DocsSidebarProps) {
  const [query, setQuery] = useState("");
  const grouped = useMemo(() => groupFiltered(query), [query]);
  const isEmpty = Object.values(grouped).every((bucket) => bucket.length === 0);

  return (
    <aside
      className={
        className ??
        "bg-surface border-r border-zinc-200 px-4 py-6 sticky top-16 self-start max-h-[calc(100vh-4rem)] overflow-y-auto w-[280px] shrink-0 hidden lg:block"
      }
    >
      <div className="mb-5">
        <DocsSearch value={query} onChange={setQuery} />
      </div>
      <nav className="flex flex-col gap-5">
        {DOC_CATEGORIES.map((category) => {
          const entries = grouped[category] ?? [];
          if (entries.length === 0) return null;
          return (
            <div key={category}>
              <p className="eyebrow text-[10px] mb-2 px-2">{category}</p>
              <ul className="flex flex-col gap-0.5">
                {entries.map((doc) => (
                  <li key={doc.id}>
                    <NavLink
                      to={`/docs/${doc.id}`}
                      end
                      className={({ isActive }) => {
                        const base =
                          "block rounded-md px-2 py-1.5 text-[13px] transition-colors focus-ring";
                        if (showActive && isActive) {
                          return `${base} bg-zinc-100 text-ink font-medium`;
                        }
                        return `${base} text-ink-3 hover:text-ink hover:bg-zinc-100/70`;
                      }}
                    >
                      {doc.title}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
        {isEmpty && (
          <p className="text-[12.5px] text-ink-4 px-2">
            No docs match <span className="font-mono text-ink-3">{query}</span>.
          </p>
        )}
      </nav>
    </aside>
  );
}

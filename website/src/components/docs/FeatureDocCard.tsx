import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

import type { DocEntry } from "@/data/docs-content";

interface FeatureDocCardProps {
  doc: DocEntry;
}

export function FeatureDocCard({ doc }: FeatureDocCardProps) {
  return (
    <Link
      to={`/docs/${doc.id}`}
      className="group block rounded-xl border border-zinc-200 bg-surface p-5 hover:border-zinc-300 hover:shadow-soft transition-all focus-ring"
    >
      <div className="flex items-start justify-between gap-3 mb-1">
        <p className="eyebrow text-[10px]">{doc.category}</p>
        <ArrowUpRight className="h-4 w-4 text-ink-4 group-hover:text-ink transition-colors" aria-hidden="true" />
      </div>
      <h3 className="text-[15px] font-semibold text-ink leading-snug">{doc.title}</h3>
      <p className="mt-1.5 text-[12.5px] text-ink-3 leading-relaxed">{doc.summary}</p>
      {doc.relatedFeatures && doc.relatedFeatures.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-1.5">
          {doc.relatedFeatures.map((feature) => (
            <li
              key={feature}
              className="px-2 py-0.5 rounded-full bg-zinc-100 text-ink-3 text-[11px] font-mono"
            >
              {feature}
            </li>
          ))}
        </ul>
      )}
      <span className="mt-4 inline-flex items-center text-[12.5px] font-medium text-brand-600 group-hover:text-brand-700">
        Read
        <span className="ml-1" aria-hidden="true">
          &rarr;
        </span>
      </span>
    </Link>
  );
}

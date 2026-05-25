import { Link } from "react-router-dom";

import { DOCS, type DocEntry, type DocSection } from "@/data/docs-content";

interface DocsPageProps {
  doc: DocEntry;
}

function resolveRelatedId(label: string): string | undefined {
  const lower = label.toLowerCase();
  const direct = DOCS.find((d) => d.title.toLowerCase() === lower);
  if (direct) return direct.id;
  const fuzzy = DOCS.find(
    (d) =>
      d.title.toLowerCase().includes(lower) ||
      lower.includes(d.title.toLowerCase()),
  );
  return fuzzy?.id;
}

function Section({ section }: { section: DocSection }) {
  return (
    <section>
      <h2 className="text-[20px] font-semibold mt-10 mb-3 text-ink tracking-tight">
        {section.heading}
      </h2>
      <p className="text-[14px] leading-relaxed text-ink-2">{section.content}</p>
      {section.bulletPoints && section.bulletPoints.length > 0 && (
        <ul className="list-disc pl-5 space-y-1 text-[14px] text-ink-2 mt-3">
          {section.bulletPoints.map((point, idx) => (
            <li key={idx}>{point}</li>
          ))}
        </ul>
      )}
      {section.codeBlock && (
        <pre className="bg-zinc-900 text-zinc-100 rounded-lg p-4 font-mono text-[12px] overflow-x-auto mt-4">
          <code>{section.codeBlock.code}</code>
        </pre>
      )}
    </section>
  );
}

export function DocsPage({ doc }: DocsPageProps) {
  return (
    <article className="max-w-[760px]">
      <p className="eyebrow mb-3">{doc.category}</p>
      <h1 className="text-[30px] md:text-[34px] font-semibold tracking-tight text-ink leading-tight">
        {doc.title}
      </h1>
      <p className="mt-3 text-[15px] leading-relaxed text-ink-3">{doc.summary}</p>

      {doc.sections.map((section, idx) => (
        <Section key={idx} section={section} />
      ))}

      {doc.relatedFeatures && doc.relatedFeatures.length > 0 && (
        <footer className="mt-14 pt-6 border-t border-zinc-200">
          <p className="eyebrow mb-3">Related</p>
          <ul className="flex flex-wrap gap-2">
            {doc.relatedFeatures.map((feature) => {
              const id = resolveRelatedId(feature);
              const className =
                "px-3 py-1 rounded-full bg-zinc-100 text-ink-2 text-[12px] font-mono hover:bg-zinc-200 transition-colors focus-ring";
              return (
                <li key={feature}>
                  {id ? (
                    <Link to={`/docs/${id}`} className={className}>
                      {feature}
                    </Link>
                  ) : (
                    <span className={className.replace("hover:bg-zinc-200 ", "")}>
                      {feature}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </footer>
      )}
    </article>
  );
}

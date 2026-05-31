"use client";

/**
 * MarkdownView — rich, themed Markdown renderer (react-markdown + remark-gfm).
 *
 * Used for human-readable artifacts (.md), requirements, and any model output.
 * GFM enabled: tables, task lists, strikethrough, autolinks. Styled with the
 * app token system; code blocks get a monospace surface. react-markdown emits
 * React nodes (no dangerouslySetInnerHTML) so text is escaped safely.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

export function MarkdownView({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cn("hx-md text-[13px] leading-relaxed text-ink-2", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h1 className="text-[18px] font-semibold text-ink mt-4 mb-2 first:mt-0" {...p} />,
          h2: (p) => <h2 className="text-[15.5px] font-semibold text-ink mt-4 mb-1.5" {...p} />,
          h3: (p) => <h3 className="text-[13.5px] font-semibold text-ink mt-3 mb-1" {...p} />,
          h4: (p) => <h4 className="text-[12.5px] font-semibold text-ink-2 mt-2 mb-1 uppercase tracking-wide" {...p} />,
          p: (p) => <p className="my-2" {...p} />,
          a: (p) => <a className="text-[var(--con-brand)] hover:underline" target="_blank" rel="noreferrer" {...p} />,
          ul: (p) => <ul className="my-2 ml-5 list-disc space-y-1" {...p} />,
          ol: (p) => <ol className="my-2 ml-5 list-decimal space-y-1" {...p} />,
          li: (p) => <li className="pl-0.5" {...p} />,
          blockquote: (p) => <blockquote className="my-2 border-l-2 border-hx-2 pl-3 text-ink-3 italic" {...p} />,
          hr: () => <hr className="my-4 border-hx" />,
          strong: (p) => <strong className="font-semibold text-ink" {...p} />,
          table: (p) => <div className="my-3 overflow-x-auto rounded-[8px] border border-hx"><table className="w-full text-[12.5px] border-collapse" {...p} /></div>,
          thead: (p) => <thead className="bg-app-2" {...p} />,
          th: (p) => <th className="text-left font-semibold text-ink px-3 py-1.5 border-b border-hx" {...p} />,
          td: (p) => <td className="px-3 py-1.5 border-b border-hx text-ink-2 align-top" {...p} />,
          code: ({ className: c, children, ...rest }) => {
            const isBlock = /language-/.test(c || "");
            if (isBlock) {
              return <code className={cn("font-mono text-[12px]", c)} {...rest}>{children}</code>;
            }
            return <code className="font-mono text-[12px] px-1 py-0.5 rounded bg-app-2 text-ink" {...rest}>{children}</code>;
          },
          pre: (p) => <pre className="my-3 overflow-x-auto rounded-lg border border-hx bg-app-2 p-3 text-[12px] leading-relaxed" {...p} />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

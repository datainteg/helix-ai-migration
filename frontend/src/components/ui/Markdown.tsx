"use client";

/**
 * frontend/src/components/ui/Markdown.tsx
 *
 * Tiny, dependency-free Markdown renderer for the Ask Helix assistant bubbles.
 *
 * Supports the common subset emitted by the model:
 *   - **bold**, *italic* / _italic_, `inline code`, [links](url)
 *   - ``` fenced code blocks ``` (optional language hint)
 *   - "- " / "* " bullet lists and "1." ordered lists
 *   - "#".."######" headings
 *   - paragraphs + single line breaks
 *
 * Safety: model text is NEVER passed to dangerouslySetInnerHTML. Everything is
 * emitted as React nodes / plain strings, so React escapes all text for us and
 * no HTML injection is possible. The parser is also defensive about partial or
 * malformed output (unclosed fences, dangling markers, empty lines).
 *
 * Light-themed via existing token aliases: bg-app-2, text-ink/-2/-3, border-hx,
 * font-mono, and --con-brand for links.
 */

import React from "react";
import { cn } from "@/lib/utils";

type Props = {
  text: string;
  className?: string;
};

/* ----------------------------- inline parsing ----------------------------- */

// Only schemes we trust for the href. Anything else is rendered as plain text
// so a model can't smuggle in javascript:/data: URLs.
function safeHref(url: string): string | null {
  const u = url.trim();
  if (/^(https?:\/\/|mailto:|\/)/i.test(u)) return u;
  return null;
}

let keySeed = 0;
const nextKey = () => `md-${keySeed++}`;

/**
 * Parse inline markdown within a single line of text into React nodes.
 * Handles (in priority order): inline code, bold, italic, links.
 * Unmatched markers are emitted verbatim, so partial output degrades cleanly.
 */
function parseInline(input: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let rest = input;

  // Matches the FIRST of: `code`, **bold**, *italic*, _italic_, [text](href).
  // Bold uses a non-greedy [\s\S]+? (not [^*]+) so it can wrap nested inline
  // markers like **bold *italic* inside** — parseInline recurses on the body.
  const pattern =
    /(`[^`]+`)|(\*\*[\s\S]+?\*\*)|(\*[^*\n]+\*)|(_[^_\n]+_)|(\[[^\]]+\]\([^)\s]+\))/;

  let guard = 0;
  while (rest.length > 0 && guard++ < 5000) {
    const m = pattern.exec(rest);
    if (!m) {
      nodes.push(rest);
      break;
    }

    const idx = m.index;
    if (idx > 0) nodes.push(rest.slice(0, idx));

    const token = m[0];

    if (token.startsWith("`")) {
      nodes.push(
        <code
          key={nextKey()}
          className="rounded bg-app-2 px-1 py-0.5 font-mono text-[0.92em] text-ink-2"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("**")) {
      nodes.push(
        <strong key={nextKey()} className="font-semibold text-ink">
          {parseInline(token.slice(2, -2))}
        </strong>
      );
    } else if (token.startsWith("*") || token.startsWith("_")) {
      nodes.push(
        <em key={nextKey()} className="italic">
          {parseInline(token.slice(1, -1))}
        </em>
      );
    } else {
      // link: [label](href)
      const lm = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(token);
      if (lm) {
        const href = safeHref(lm[2]);
        if (href) {
          nodes.push(
            <a
              key={nextKey()}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium underline underline-offset-2"
              style={{ color: "var(--con-brand)" }}
            >
              {parseInline(lm[1])}
            </a>
          );
        } else {
          nodes.push(lm[1]); // untrusted scheme -> render label as plain text
        }
      } else {
        nodes.push(token);
      }
    }

    rest = rest.slice(idx + token.length);
  }

  return nodes;
}

/* ------------------------------ block parsing ------------------------------ */

type Block =
  | { type: "code"; lang: string; content: string }
  | { type: "heading"; level: number; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "p"; lines: string[] };

function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  const isUl = (l: string) => /^\s*[-*]\s+/.test(l);
  const isOl = (l: string) => /^\s*\d+\.\s+/.test(l);

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block. Tolerates a missing closing fence (eats to EOF).
    const fence = /^\s*```(.*)$/.exec(line);
    if (fence) {
      const lang = fence[1].trim();
      const body: string[] = [];
      i++;
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) {
        body.push(lines[i]);
        i++;
      }
      if (i < lines.length) i++; // skip closing fence if present
      blocks.push({ type: "code", lang, content: body.join("\n") });
      continue;
    }

    // Blank line -> separator
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Heading
    const h = /^\s*(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      blocks.push({ type: "heading", level: h[1].length, text: h[2].trim() });
      i++;
      continue;
    }

    // Unordered list
    if (isUl(line)) {
      const items: string[] = [];
      while (i < lines.length && isUl(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Ordered list
    if (isOl(line)) {
      const items: string[] = [];
      while (i < lines.length && isOl(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    // Paragraph: consume consecutive non-blank, non-special lines
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^\s*```/.test(lines[i]) &&
      !/^\s*#{1,6}\s+/.test(lines[i]) &&
      !isUl(lines[i]) &&
      !isOl(lines[i])
    ) {
      para.push(lines[i]);
      i++;
    }
    if (para.length) blocks.push({ type: "p", lines: para });
  }

  return blocks;
}

/* ------------------------------- rendering -------------------------------- */

function HeadingTag({ level, text }: { level: number; text: string }) {
  const sizes: Record<number, string> = {
    1: "text-[15px] font-semibold",
    2: "text-[14px] font-semibold",
    3: "text-[13px] font-semibold",
    4: "text-[12.5px] font-semibold",
    5: "text-[12.5px] font-semibold",
    6: "text-[12.5px] font-semibold",
  };
  const Tag = (`h${level}` as unknown) as keyof JSX.IntrinsicElements;
  return (
    <Tag className={cn("mt-1 mb-0.5 text-ink", sizes[level] ?? sizes[6])}>
      {parseInline(text)}
    </Tag>
  );
}

function renderLines(lines: string[]): React.ReactNode[] {
  // Within a paragraph each newline becomes a soft <br/>.
  const out: React.ReactNode[] = [];
  lines.forEach((ln, idx) => {
    if (idx > 0) out.push(<br key={nextKey()} />);
    out.push(...parseInline(ln));
  });
  return out;
}

export function Markdown({ text, className }: Props) {
  // Defensive: never throw on odd input, just show what we got.
  const safe = typeof text === "string" ? text : String(text ?? "");
  const blocks = React.useMemo(() => parseBlocks(safe), [safe]);

  return (
    <div className={cn("space-y-2 text-[12.5px] leading-relaxed text-ink", className)}>
      {blocks.map((b) => {
        switch (b.type) {
          case "code":
            return (
              <pre
                key={nextKey()}
                className="overflow-x-auto rounded-lg border border-hx bg-app-2 p-2.5"
              >
                <code className="font-mono text-[12px] leading-relaxed text-ink-2">
                  {b.content}
                </code>
              </pre>
            );
          case "heading":
            return <HeadingTag key={nextKey()} level={b.level} text={b.text} />;
          case "ul":
            return (
              <ul key={nextKey()} className="ml-4 list-disc space-y-1 marker:text-ink-3">
                {b.items.map((it) => (
                  <li key={nextKey()}>{parseInline(it)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={nextKey()} className="ml-4 list-decimal space-y-1 marker:text-ink-3">
                {b.items.map((it) => (
                  <li key={nextKey()}>{parseInline(it)}</li>
                ))}
              </ol>
            );
          case "p":
          default:
            return (
              <p key={nextKey()} className="break-words">
                {renderLines(b.lines)}
              </p>
            );
        }
      })}
    </div>
  );
}

export default Markdown;

"use client";

/**
 * Zero-dependency code viewer for the Developer Workspace.
 *
 * No syntax-highlight library is installed in this app (checked package.json:
 * no shiki / prismjs / react-syntax-highlighter / highlight.js / monaco /
 * codemirror), and the task forbids adding heavy deps. So this is a small
 * regex-based tokenizer that covers the languages the artifact registry deals
 * with (SQL, JS/TS, Python, JSON, YAML, shell) well enough to be readable.
 *
 * It renders a proper monospace block with line numbers, a language label,
 * a copy button, and horizontal scroll, themed with the repo token classes.
 */

import { useMemo, useState } from "react";
import { Check, Copy } from "lucide-react";

type Token = { text: string; cls: string };

const KEYWORDS: Record<string, RegExp> = {
  sql: /\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|CREATE|ALTER|DROP|TABLE|INDEX|VIEW|INTO|VALUES|SET|AS|AND|OR|NOT|NULL|IS|IN|LIKE|BETWEEN|DISTINCT|UNION|ALL|PRIMARY|KEY|FOREIGN|REFERENCES|CONSTRAINT|DEFAULT|CASCADE|BEGIN|COMMIT|ROLLBACK|TRANSACTION|ADD|COLUMN|RENAME|TRUNCATE|GRANT|REVOKE|WITH|CASE|WHEN|THEN|ELSE|END|EXISTS|UNIQUE)\b/gi,
  python: /\b(def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|finally|raise|yield|lambda|pass|break|continue|global|nonlocal|assert|async|await|None|True|False|self)\b/g,
  ts: /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|class|extends|implements|interface|type|enum|import|export|from|as|default|async|await|try|catch|finally|throw|typeof|instanceof|void|null|undefined|true|false|this|super|public|private|protected|readonly|static|yield)\b/g,
};

function pickLang(lang?: string): keyof typeof KEYWORDS | "json" | "yaml" | "shell" | "plain" {
  const l = (lang || "").toLowerCase();
  if (/\bsql\b/.test(l)) return "sql";
  if (/\b(py|python)\b/.test(l)) return "python";
  if (/\b(ts|tsx|js|jsx|javascript|typescript)\b/.test(l)) return "ts";
  if (/\b(json)\b/.test(l)) return "json";
  if (/\b(ya?ml)\b/.test(l)) return "yaml";
  if (/\b(sh|bash|shell|zsh)\b/.test(l)) return "shell";
  return "plain";
}

/**
 * Tokenize a single line. We protect strings / comments / numbers first by
 * splitting on a master regex, then keyword-highlight the remaining plain runs.
 * It's deliberately simple — readable, not a full parser.
 */
function tokenizeLine(line: string, lang: ReturnType<typeof pickLang>): Token[] {
  // Master pattern: line/block-ish comments, double & single quoted strings, numbers.
  const master = /(--[^\n]*|#[^\n]*|\/\/[^\n]*|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|\b\d[\d_.]*\b)/g;
  const out: Token[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = master.exec(line)) !== null) {
    if (m.index > last) out.push(...keywordPass(line.slice(last, m.index), lang));
    const tok = m[0];
    let cls = "tok-str";
    if (tok.startsWith("--") || tok.startsWith("#") || tok.startsWith("//")) cls = "tok-com";
    else if (/^[\d]/.test(tok)) cls = "tok-num";
    out.push({ text: tok, cls });
    last = m.index + tok.length;
  }
  if (last < line.length) out.push(...keywordPass(line.slice(last), lang));
  return out;
}

function keywordPass(text: string, lang: ReturnType<typeof pickLang>): Token[] {
  const kw = (KEYWORDS as Record<string, RegExp>)[lang];
  if (!kw) return [{ text, cls: "tok-plain" }];
  const re = new RegExp(kw.source, kw.flags.includes("g") ? kw.flags : kw.flags + "g");
  const out: Token[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), cls: "tok-plain" });
    out.push({ text: m[0], cls: "tok-kw" });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), cls: "tok-plain" });
  return out;
}

const CLS: Record<string, string> = {
  "tok-plain": "text-ink-2",
  "tok-kw": "text-helix-600 font-medium",
  "tok-str": "text-emerald-600",
  "tok-num": "text-amber-600",
  "tok-com": "text-ink-4 italic",
};

export function CodeBlock({
  code,
  language,
  filename,
  maxHeight = 520,
}: {
  code: string;
  language?: string;
  filename?: string;
  maxHeight?: number;
}) {
  const [copied, setCopied] = useState(false);
  const lang = useMemo(() => pickLang(language || filename?.split(".").pop()), [language, filename]);
  const lines = useMemo(() => code.replace(/\n$/, "").split("\n"), [code]);
  const gutterW = String(lines.length).length;

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked — no-op */
    }
  }

  return (
    <div className="rounded-lg border border-hx bg-app-2 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-hx bg-surface">
        <span className="text-[11px] uppercase tracking-wider font-medium text-ink-4">
          {language || lang}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 text-[11.5px] text-ink-3 hover:text-ink rounded px-1.5 py-0.5 hover:bg-app-2"
        >
          {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="overflow-auto" style={{ maxHeight }}>
        <pre className="text-[12.5px] leading-[1.6] font-mono">
          <code>
            {lines.map((line, i) => (
              <div key={i} className="flex hover:bg-surface/60 px-3">
                <span
                  className="select-none text-right text-ink-4 pr-3 shrink-0 tabular-nums"
                  style={{ width: `${gutterW + 1}ch` }}
                >
                  {i + 1}
                </span>
                <span className="whitespace-pre flex-1">
                  {line.length === 0
                    ? " "
                    : tokenizeLine(line, lang).map((t, j) => (
                        <span key={j} className={CLS[t.cls] || CLS["tok-plain"]}>
                          {t.text}
                        </span>
                      ))}
                </span>
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}

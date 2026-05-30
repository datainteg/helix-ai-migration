"use client";

/**
 * Ask Helix — the in-app Help agent.
 *
 * A trigger button (matching the Topbar's affordance) that opens a light-themed
 * chat popup. The agent is grounded server-side to guide users on how Helix
 * works; this component just streams turns to POST /api/v1/assistant/ask.
 */

import { useEffect, useRef, useState } from "react";
import { Sparkles, X, Send, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { Markdown } from "@/components/ui/Markdown";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type Role = "user" | "assistant";
interface Turn {
  role: Role;
  content: string;
}

const GREETING: Turn = {
  role: "assistant",
  content:
    "Hi! I'm your Helix guide. Ask me how anything works — connecting databases, running the AI migration pipeline, reconciliation, or where to find a feature.",
};

const SUGGESTIONS = [
  "How do I start a migration?",
  "What does the Reconciler do?",
  "How do I connect a source database?",
];

export function AskHelix() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keep the message list pinned to the latest turn.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  // Focus the input when the panel opens; close on Escape.
  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || loading) return;
    setError("");
    setInput("");
    const history = turns.filter((t) => t !== GREETING);
    const next = [...turns, { role: "user" as Role, content: message }];
    setTurns(next);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/assistant/ask`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
      });
      if (!res.ok) {
        let detail = "The assistant couldn't answer right now.";
        try { const j = await res.json(); if (j?.detail) detail = typeof j.detail === "string" ? j.detail : detail; } catch { /* keep default */ }
        throw new Error(detail);
      }
      const data = await res.json();
      setTurns((cur) => [...cur, { role: "assistant", content: String(data.answer ?? "") }]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Trigger — mirrors the original Ask Helix affordance */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          "hidden sm:inline-flex items-center gap-1.5 h-8 px-2.5 border rounded-md text-[11.5px] transition-colors",
          open
            ? "border-[var(--con-brand)] bg-app-2 text-ink"
            : "border-hx-2 bg-surface text-ink-2 hover:bg-app-2"
        )}
      >
        <Sparkles className="h-[13px] w-[13px] text-[var(--con-brand)]" />
        <span>Ask Helix</span>
      </button>

      {open && (
        <>
          {/* Click-away scrim (transparent; keeps the rest of the app interactive-looking but dismisses on outside click) */}
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 cursor-default"
          />
          <div
            role="dialog"
            aria-label="Ask Helix"
            className="fixed z-50 right-3 sm:right-6 top-[52px] w-[min(380px,calc(100vw-1.5rem))] flex flex-col rounded-xl border border-hx bg-surface shadow-[0_24px_60px_-24px_rgba(10,10,10,0.45)] overflow-hidden"
            style={{ maxHeight: "min(560px, calc(100vh - 76px))" }}
          >
            {/* Header */}
            <div className="flex items-center gap-2.5 px-4 py-3 border-b border-hx bg-surface-hi">
              <span
                className="grid place-items-center h-7 w-7 rounded-lg text-white"
                style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}
              >
                <Sparkles className="h-3.5 w-3.5" />
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold text-ink leading-tight">Ask Helix</div>
                <div className="text-[10.5px] text-ink-4">Your guide to how Helix works</div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="p-1.5 rounded-md text-ink-4 hover:text-ink hover:bg-app-2 focus-ring"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-3.5 py-3.5 flex flex-col gap-3">
              {turns.map((t, i) => (
                <Bubble key={i} turn={t} />
              ))}
              {loading && (
                <div className="flex items-start gap-2">
                  <BotAvatar />
                  <div className="rounded-2xl rounded-tl-sm bg-app-2 px-3 py-2 text-[12.5px] text-ink-3">
                    <span className="inline-flex gap-1">
                      <Dot /> <Dot delay="150ms" /> <Dot delay="300ms" />
                    </span>
                  </div>
                </div>
              )}
              {error && (
                <div className="rounded-lg border border-[var(--con-err)]/30 bg-[var(--con-err)]/8 px-3 py-2 text-[12px] text-[var(--con-err)]">
                  {error}
                </div>
              )}

              {/* Starter suggestions — only before the first user turn */}
              {turns.length === 1 && !loading && (
                <div className="flex flex-col gap-1.5 pt-1">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => send(s)}
                      className="text-left text-[12px] text-ink-2 border border-hx-2 rounded-lg px-3 py-2 hover:bg-app-2 hover:border-[var(--con-brand)]/40 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Composer */}
            <form
              onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="flex items-center gap-2 px-3 py-3 border-t border-hx bg-surface-hi"
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask how Helix works…"
                maxLength={4000}
                className="flex-1 h-9 rounded-lg border border-hx-2 bg-surface px-3 text-[12.5px] text-ink placeholder-ink-4 outline-none focus:border-[var(--con-brand)]/60 focus:ring-2 focus:ring-[var(--con-brand)]/15 transition"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                aria-label="Send"
                className="grid place-items-center h-9 w-9 rounded-lg text-white transition disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
                style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </div>
        </>
      )}
    </>
  );
}

function BotAvatar() {
  return (
    <span
      className="grid place-items-center h-7 w-7 flex-shrink-0 rounded-lg text-white"
      style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}
    >
      <Bot className="h-3.5 w-3.5" />
    </span>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        {/* Brand-indigo bubble, white text (~8:1 AA/AAA), brand-tinted glow.
            Distinct in hue from the near-white bot bubble; holds in dark mode
            since --con-brand isn't remapped there. */}
        <div className="max-w-[82%] rounded-2xl rounded-tr-sm bg-con-brand text-white shadow-glow px-3 py-2 text-[12.5px] leading-relaxed whitespace-pre-wrap break-words">
          {turn.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2">
      <BotAvatar />
      {/* Markdown renders its own block spacing — no whitespace-pre-wrap here. */}
      <div className="max-w-[82%] rounded-2xl rounded-tl-sm bg-app-2 text-ink px-3 py-2 break-words">
        <Markdown text={turn.content} />
      </div>
    </div>
  );
}

function Dot({ delay = "0ms" }: { delay?: string }) {
  return (
    <span
      className="h-1.5 w-1.5 rounded-full bg-ink-4 motion-safe:animate-bounce"
      style={{ animationDelay: delay, animationDuration: "1s" }}
    />
  );
}

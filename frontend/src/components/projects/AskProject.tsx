"use client";

/**
 * AskProject — the project-aware orchestrator chat ("Ask Helix about this").
 *
 * A themed popup bound to ONE project. It posts to /assistant/ask-project, which
 * runs a LangGraph orchestrator grounded in the project's real status, workflow
 * runs (live step status), artifacts, and recon/validation. Controlled by the
 * "Ask Helix about this" button on the project detail page.
 */

import { useEffect, useRef, useState } from "react";
import { Sparkles, X, Send, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { Markdown } from "@/components/ui/Markdown";
import { askProject, type ChatTurn } from "@/lib/projects/api";

const SUGGESTIONS = [
  "What's the current status of this project?",
  "Has any workflow run yet, and what happened?",
  "Explain the latest artifact",
  "Is anything on hold or blocking progress?",
];

export function AskProject({ projectId, projectName, open, onClose }: {
  projectId: string;
  projectName: string;
  open: boolean;
  onClose: () => void;
}) {
  const greeting: ChatTurn = {
    role: "assistant",
    content: `Hi! I'm the orchestrator for **${projectName}**. Ask me about its status, agent runs, artifacts, or reconciliation — I read this project's real data to answer.`,
  };
  const [turns, setTurns] = useState<ChatTurn[]>([greeting]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Re-seed the greeting if the project name resolves AFTER mount (the parent
  // mounts this before the project fetch returns), but only while the chat is
  // still just the greeting — never clobber an in-progress conversation.
  useEffect(() => {
    setTurns((cur) => (cur.length === 1 && cur[0].role === "assistant")
      ? [{ role: "assistant", content: `Hi! I'm the orchestrator for **${projectName}**. Ask me about its status, agent runs, artifacts, or reconciliation — I read this project's real data to answer.` }]
      : cur);
  }, [projectName]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, loading]);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || loading) return;
    setError(""); setInput("");
    const history = turns.filter((t) => t !== greeting);
    setTurns((cur) => [...cur, { role: "user", content: message }]);
    setLoading(true);
    try {
      const { answer } = await askProject(projectId, message, history);
      setTurns((cur) => [...cur, { role: "assistant", content: String(answer ?? "") }]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The project assistant couldn't answer right now.");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <button type="button" aria-hidden tabIndex={-1} onClick={onClose} className="fixed inset-0 z-40 cursor-default" />
      <div
        role="dialog"
        aria-label={`Ask Helix about ${projectName}`}
        className="fixed z-50 right-3 sm:right-6 top-[52px] w-[min(420px,calc(100vw-1.5rem))] flex flex-col rounded-xl border border-hx bg-surface shadow-[0_24px_60px_-24px_rgba(10,10,10,0.45)] overflow-hidden"
        style={{ maxHeight: "min(600px, calc(100vh - 76px))" }}
      >
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-hx bg-surface-hi">
          <span className="grid place-items-center h-7 w-7 rounded-lg text-white" style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}>
            <Sparkles className="h-3.5 w-3.5" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold text-ink leading-tight">Ask Helix · this project</div>
            <div className="text-[10.5px] text-ink-4 truncate">{projectName}</div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1.5 rounded-md text-ink-4 hover:text-ink hover:bg-app-2 focus-ring">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-3.5 py-3.5 flex flex-col gap-3">
          {turns.map((t, i) => <Bubble key={i} turn={t} />)}
          {loading && (
            <div className="flex items-start gap-2">
              <BotAvatar />
              <div className="rounded-2xl rounded-tl-sm bg-app-2 px-3 py-2 text-[12.5px] text-ink-3">
                <span className="inline-flex gap-1"><Dot /> <Dot delay="150ms" /> <Dot delay="300ms" /></span>
              </div>
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-[var(--con-err)]/30 bg-[var(--con-err)]/8 px-3 py-2 text-[12px] text-[var(--con-err)]">{error}</div>
          )}
          {turns.length === 1 && !loading && (
            <div className="flex flex-col gap-1.5 pt-1">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => send(s)}
                  className="text-left text-[12px] text-ink-2 border border-hx-2 rounded-lg px-3 py-2 hover:bg-app-2 hover:border-[var(--con-brand)]/40 transition-colors">
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2 px-3 py-3 border-t border-hx bg-surface-hi">
          <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about this project…" maxLength={4000}
            className="flex-1 h-9 rounded-lg border border-hx-2 bg-surface px-3 text-[12.5px] text-ink placeholder-ink-4 outline-none focus:border-[var(--con-brand)]/60 focus:ring-2 focus:ring-[var(--con-brand)]/15 transition" />
          <button type="submit" disabled={!input.trim() || loading} aria-label="Send"
            className="grid place-items-center h-9 w-9 rounded-lg text-white transition disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
            style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}>
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </>
  );
}

function BotAvatar() {
  return (
    <span className="grid place-items-center h-7 w-7 flex-shrink-0 rounded-lg text-white" style={{ background: "linear-gradient(135deg,#4F46E5,#06B6D4)" }}>
      <Bot className="h-3.5 w-3.5" />
    </span>
  );
}

function Bubble({ turn }: { turn: ChatTurn }) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[82%] rounded-2xl rounded-tr-sm bg-con-brand text-white shadow-glow px-3 py-2 text-[12.5px] leading-relaxed whitespace-pre-wrap break-words">
          {turn.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2">
      <BotAvatar />
      <div className="max-w-[82%] rounded-2xl rounded-tl-sm bg-app-2 text-ink px-3 py-2 break-words">
        <Markdown text={turn.content} />
      </div>
    </div>
  );
}

function Dot({ delay = "0ms" }: { delay?: string }) {
  return <span className="h-1.5 w-1.5 rounded-full bg-ink-4 motion-safe:animate-bounce" style={{ animationDelay: delay, animationDuration: "1s" }} />;
}

"use client";

import { useState } from "react";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";
import { ArtifactViewer } from "./ArtifactViewer";

interface Props {
  value: string;
  onChange: (v: string) => void;
}

// Markdown editor with Edit / Preview toggle.
export function ArtifactEditor({ value, onChange }: Props) {
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        {(["edit", "preview"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              "rounded-md px-2.5 py-1 text-[12px] capitalize transition-colors",
              mode === m ? "bg-app-2 text-ink-1 font-medium" : "text-ink-3 hover:text-ink-1",
            )}
          >
            {m}
          </button>
        ))}
      </div>
      {mode === "edit" ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          className="h-[60vh] w-full resize-y rounded-md border border-hx bg-app px-3 py-2 font-mono text-[12.5px] leading-relaxed text-ink-1 focus:border-helix-400 focus:outline-none"
        />
      ) : (
        <div className="min-h-[60vh] rounded-md border border-hx bg-app px-4 py-3">
          <ArtifactViewer markdown={value} />
        </div>
      )}
    </div>
  );
}

// Small download helper reused by the review page.
export function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename.endsWith(".md") ? filename : `${filename}.md`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

export function DownloadButton({ filename, content }: { filename: string; content: string }) {
  return <Button variant="ghost" onClick={() => downloadMarkdown(filename, content)}>Download</Button>;
}

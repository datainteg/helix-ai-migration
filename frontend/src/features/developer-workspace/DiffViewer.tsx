"use client";

import { useState } from "react";

type DiffViewerProps = {
  original: string;
  generated: string;
  approvalStatus?: "draft" | "approved" | "rejected";
};

export default function DiffViewer({ original, generated, approvalStatus = "draft" }: DiffViewerProps) {
  const [view, setView] = useState<"side-by-side" | "unified">("side-by-side");

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs">
        <button onClick={() => setView("side-by-side")} className={`px-2 py-1 rounded ${view === "side-by-side" ? "bg-gray-200 font-medium" : ""}`}>
          Side by Side
        </button>
        <button onClick={() => setView("unified")} className={`px-2 py-1 rounded ${view === "unified" ? "bg-gray-200 font-medium" : ""}`}>
          Unified
        </button>
        <span className={`ml-auto px-2 py-0.5 rounded text-xs font-medium ${
          approvalStatus === "approved" ? "bg-green-100 text-green-700" :
          approvalStatus === "rejected" ? "bg-red-100 text-red-700" :
          "bg-amber-100 text-amber-700"
        }`}>
          {approvalStatus.toUpperCase()}
        </span>
      </div>

      {view === "side-by-side" ? (
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div className="rounded border p-3 bg-gray-50 whitespace-pre-wrap min-h-[200px]">{original || "// Original source"}</div>
          <div className="rounded border p-3 bg-amber-50 whitespace-pre-wrap min-h-[200px] border-dashed">{generated || "// Generated draft"}</div>
        </div>
      ) : (
        <div className="rounded border p-3 bg-gray-50 text-xs font-mono whitespace-pre-wrap min-h-[200px]">
          <span className="text-red-500">--- Original</span>
          {"\n"}{original || "// Original source"}
          {"\n"}<span className="text-green-500">+++ Generated</span>
          {"\n"}{generated || "// Generated draft"}
        </div>
      )}
    </div>
  );
}

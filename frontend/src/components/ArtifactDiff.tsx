"use client";

import { useMemo } from "react";

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  content: string;
  lineNo: number;
}

function computeDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const result: DiffLine[] = [];

  // Simple LCS-based diff (Myers-lite for display purposes)
  const oldSet = new Set(oldLines);
  const newSet = new Set(newLines);

  let oi = 0;
  let ni = 0;
  let lineNo = 1;

  while (oi < oldLines.length || ni < newLines.length) {
    const oldLine = oldLines[oi];
    const newLine = newLines[ni];

    if (oi >= oldLines.length) {
      result.push({ type: "added", content: newLine, lineNo: lineNo++ });
      ni++;
    } else if (ni >= newLines.length) {
      result.push({ type: "removed", content: oldLine, lineNo: lineNo++ });
      oi++;
    } else if (oldLine === newLine) {
      result.push({ type: "unchanged", content: oldLine, lineNo: lineNo++ });
      oi++;
      ni++;
    } else {
      result.push({ type: "removed", content: oldLine, lineNo: lineNo++ });
      result.push({ type: "added", content: newLine, lineNo: lineNo++ });
      oi++;
      ni++;
    }
  }
  return result;
}

interface ArtifactDiffProps {
  oldContent: string;
  newContent: string;
  oldLabel?: string;
  newLabel?: string;
  className?: string;
}

export function ArtifactDiff({
  oldContent,
  newContent,
  oldLabel = "Previous",
  newLabel = "Current",
  className = "",
}: ArtifactDiffProps) {
  const lines = useMemo(() => computeDiff(oldContent, newContent), [oldContent, newContent]);

  const added = lines.filter((l) => l.type === "added").length;
  const removed = lines.filter((l) => l.type === "removed").length;

  return (
    <div className={`rounded-xl border bg-white shadow-sm overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-4 py-2 border-b bg-gray-50 text-sm">
        <div className="flex items-center gap-4">
          <span className="font-medium text-gray-700">{oldLabel} → {newLabel}</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-600 font-medium">+{added}</span>
          <span className="text-red-600 font-medium">−{removed}</span>
        </div>
      </div>

      <div className="overflow-auto max-h-[600px]">
        <table className="w-full text-xs font-mono">
          <tbody>
            {lines.map((line, i) => (
              <tr
                key={i}
                className={
                  line.type === "added"
                    ? "bg-green-50"
                    : line.type === "removed"
                    ? "bg-red-50"
                    : ""
                }
              >
                <td className="select-none px-3 py-0.5 text-right text-gray-400 border-r border-gray-100 w-10">
                  {line.lineNo}
                </td>
                <td className="px-2 py-0.5 w-5 select-none">
                  {line.type === "added" ? (
                    <span className="text-green-600">+</span>
                  ) : line.type === "removed" ? (
                    <span className="text-red-600">−</span>
                  ) : (
                    <span className="text-gray-300"> </span>
                  )}
                </td>
                <td className="px-2 py-0.5 whitespace-pre text-gray-800">
                  {line.content}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

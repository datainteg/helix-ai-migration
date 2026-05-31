"use client";

/**
 * Zero-dependency line diff for the Developer Workspace version comparison.
 *
 * The `diff` npm package is NOT installed (checked package.json), and the task
 * forbids adding it. So this implements a real line-based LCS diff in pure JS —
 * not a fuzzy set-compare — so added/removed/unchanged lines are accurate.
 */

import { useMemo } from "react";

type Row = { kind: "add" | "del" | "same"; text: string; oldNo?: number; newNo?: number };

/** Classic dynamic-programming LCS over the two line arrays. */
function diffLines(aText: string, bText: string): Row[] {
  const a = aText.replace(/\n$/, "").split("\n");
  const b = bText.replace(/\n$/, "").split("\n");
  const n = a.length;
  const m = b.length;
  // dp[i][j] = LCS length of a[i:], b[j:]
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const rows: Row[] = [];
  let i = 0;
  let j = 0;
  let oldNo = 1;
  let newNo = 1;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      rows.push({ kind: "same", text: a[i], oldNo: oldNo++, newNo: newNo++ });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      rows.push({ kind: "del", text: a[i], oldNo: oldNo++ });
      i++;
    } else {
      rows.push({ kind: "add", text: b[j], newNo: newNo++ });
      j++;
    }
  }
  while (i < n) rows.push({ kind: "del", text: a[i++], oldNo: oldNo++ });
  while (j < m) rows.push({ kind: "add", text: b[j++], newNo: newNo++ });
  return rows;
}

const ROW_CLS: Record<Row["kind"], string> = {
  add: "bg-emerald-500/10",
  del: "bg-rose-500/10",
  same: "",
};
const TEXT_CLS: Record<Row["kind"], string> = {
  add: "text-emerald-700",
  del: "text-rose-700",
  same: "text-ink-2",
};
const SIGN: Record<Row["kind"], string> = { add: "+", del: "-", same: " " };

export function DiffView({
  oldText,
  newText,
  oldLabel = "previous",
  newLabel = "current",
  maxHeight = 520,
}: {
  oldText: string;
  newText: string;
  oldLabel?: string;
  newLabel?: string;
  maxHeight?: number;
}) {
  const rows = useMemo(() => diffLines(oldText, newText), [oldText, newText]);
  const added = rows.filter((r) => r.kind === "add").length;
  const removed = rows.filter((r) => r.kind === "del").length;
  const gutterW = Math.max(2, String(rows.length).length);

  return (
    <div className="rounded-lg border border-hx bg-app-2 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-hx bg-surface text-[11.5px]">
        <span className="text-ink-3">
          <span className="font-mono text-ink-2">{oldLabel}</span> →{" "}
          <span className="font-mono text-ink-2">{newLabel}</span>
        </span>
        <span className="flex items-center gap-2 font-mono">
          <span className="text-emerald-600">+{added}</span>
          <span className="text-rose-600">-{removed}</span>
        </span>
      </div>
      <div className="overflow-auto" style={{ maxHeight }}>
        <pre className="text-[12.5px] leading-[1.6] font-mono">
          <code>
            {rows.map((r, idx) => (
              <div key={idx} className={`flex px-3 ${ROW_CLS[r.kind]}`}>
                <span className="select-none text-right text-ink-4 pr-2 shrink-0 tabular-nums" style={{ width: `${gutterW + 1}ch` }}>
                  {r.oldNo ?? ""}
                </span>
                <span className="select-none text-right text-ink-4 pr-2 shrink-0 tabular-nums" style={{ width: `${gutterW + 1}ch` }}>
                  {r.newNo ?? ""}
                </span>
                <span className={`select-none pr-2 shrink-0 ${TEXT_CLS[r.kind]}`}>{SIGN[r.kind]}</span>
                <span className={`whitespace-pre flex-1 ${TEXT_CLS[r.kind]}`}>{r.text.length === 0 ? " " : r.text}</span>
              </div>
            ))}
          </code>
        </pre>
      </div>
    </div>
  );
}

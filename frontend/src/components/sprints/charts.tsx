"use client";

/**
 * Sprint analytics charts — lightweight inline SVG, no chart library.
 *
 * Mirrors the existing AreaChart/Sparkline patterns so the bundle stays
 * dependency-free. Reads design tokens via CSS vars (`--con-ink-1`,
 * `--con-brand`, …) so dark mode + tweaks panel work out of the box.
 */

import React from "react";

import type { BurndownPoint, VelocityPoint } from "@/lib/sprints";

const PAD_L = 36, PAD_R = 10, PAD_T = 12, PAD_B = 24;

// ── SprintBurndownChart ─────────────────────────────────────────────

export function SprintBurndownChart({
  data,
  width = 720,
  height = 220,
}: {
  data: BurndownPoint[];
  width?: number;
  height?: number;
}) {
  if (!data.length) return null;
  const w = width - PAD_L - PAD_R;
  const h = height - PAD_T - PAD_B;
  const max = Math.max(...data.map((d) => Math.max(d.ideal, d.actual)));
  const step = w / Math.max(1, data.length - 1);
  const path = (key: "ideal" | "actual") =>
    data.map((d, i) => `${i === 0 ? "M" : "L"}${PAD_L + i * step},${PAD_T + h - (d[key] / max) * h}`).join(" ");

  const ticks = 4;
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="block">
      {Array.from({ length: ticks + 1 }).map((_, i) => {
        const y = PAD_T + (h / ticks) * i;
        const v = Math.round(max - (max / ticks) * i);
        return (
          <g key={i}>
            <line x1={PAD_L} y1={y} x2={PAD_L + w} y2={y} stroke="var(--con-line)" strokeDasharray={i === ticks ? "0" : "2 3"} />
            <text x={PAD_L - 8} y={y + 4} fontSize="10" fill="var(--con-ink-4)" textAnchor="end" fontFamily="Geist Mono">{v}</text>
          </g>
        );
      })}
      <path d={path("ideal")} fill="none" stroke="var(--con-ink-4)" strokeWidth="1.5" strokeDasharray="4 4" />
      <path d={path("actual")} fill="none" stroke="var(--con-brand)" strokeWidth="2" strokeLinejoin="round" />
      {data.map((d, i) =>
        i % Math.ceil(data.length / 8) === 0 ? (
          <text
            key={i}
            x={PAD_L + i * step}
            y={PAD_T + h + 14}
            fontSize="9.5"
            fill="var(--con-ink-4)"
            textAnchor="middle"
            fontFamily="Geist Mono"
          >
            {d.date.slice(5)}
          </text>
        ) : null
      )}
      <g transform={`translate(${PAD_L + 8}, ${PAD_T + 4})`}>
        <rect width="120" height="34" fill="rgba(255,255,255,0.85)" stroke="var(--con-line)" rx="4" />
        <line x1="8" y1="12" x2="20" y2="12" stroke="var(--con-ink-4)" strokeWidth="1.5" strokeDasharray="3 3" />
        <text x="26" y="15" fontSize="10" fill="var(--con-ink-3)">Ideal</text>
        <line x1="8" y1="26" x2="20" y2="26" stroke="var(--con-brand)" strokeWidth="2" />
        <text x="26" y="29" fontSize="10" fill="var(--con-ink-3)">Actual</text>
      </g>
    </svg>
  );
}

// ── SprintVelocityChart ─────────────────────────────────────────────

export function SprintVelocityChart({
  data,
  width = 560,
  height = 220,
}: {
  data: VelocityPoint[];
  width?: number;
  height?: number;
}) {
  if (!data.length) return null;
  const w = width - PAD_L - PAD_R;
  const h = height - PAD_T - PAD_B;
  const max = Math.max(...data.flatMap((d) => [d.planned, d.delivered]));
  const groupW = w / data.length;
  const barW = Math.min(28, groupW / 3);
  const ticks = 4;
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="block">
      {Array.from({ length: ticks + 1 }).map((_, i) => {
        const y = PAD_T + (h / ticks) * i;
        const v = Math.round(max - (max / ticks) * i);
        return (
          <g key={i}>
            <line x1={PAD_L} y1={y} x2={PAD_L + w} y2={y} stroke="var(--con-line)" strokeDasharray={i === ticks ? "0" : "2 3"} />
            <text x={PAD_L - 8} y={y + 4} fontSize="10" fill="var(--con-ink-4)" textAnchor="end" fontFamily="Geist Mono">{v}</text>
          </g>
        );
      })}
      {data.map((d, i) => {
        const cx = PAD_L + i * groupW + groupW / 2;
        const hp = (d.planned   / max) * h;
        const hd = (d.delivered / max) * h;
        return (
          <g key={d.sprintLabel}>
            <rect x={cx - barW - 1}    y={PAD_T + h - hp} width={barW} height={hp} fill="var(--con-ink-4)" opacity="0.45" rx="2" />
            <rect x={cx + 1}           y={PAD_T + h - hd} width={barW} height={hd} fill="var(--con-brand)" rx="2" />
            <text x={cx} y={PAD_T + h + 14} fontSize="10" fill="var(--con-ink-3)" textAnchor="middle" fontFamily="Geist Mono">{d.sprintLabel}</text>
          </g>
        );
      })}
      <g transform={`translate(${PAD_L + 8}, ${PAD_T + 4})`}>
        <rect width="130" height="34" fill="rgba(255,255,255,0.85)" stroke="var(--con-line)" rx="4" />
        <rect x="8" y="6" width="10" height="10" fill="var(--con-ink-4)" opacity="0.45" rx="2" />
        <text x="24" y="15" fontSize="10" fill="var(--con-ink-3)">Planned</text>
        <rect x="8" y="20" width="10" height="10" fill="var(--con-brand)" rx="2" />
        <text x="24" y="29" fontSize="10" fill="var(--con-ink-3)">Delivered</text>
      </g>
    </svg>
  );
}

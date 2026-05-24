interface AreaChartProps {
  /** Either [x, y] tuples (legacy) OR { label, a, b } objects */
  data: [number | string, number][] | { label: string; a: number; b?: number }[];
  width?: number;
  height?: number;
  /** Primary line color */
  color?: string;
  /** Secondary (comparison) line color */
  color2?: string;
  /** Show second series — defaults to true if data has `b` field */
  comparison?: boolean;
}

type Row = { label: string; a: number; b?: number };

function normalize(data: AreaChartProps["data"]): Row[] {
  if (data.length === 0) return [];
  // Legacy tuple format
  if (Array.isArray(data[0])) {
    return (data as [number | string, number][]).map(([x, y]) => ({ label: String(x), a: y }));
  }
  return data as Row[];
}

/**
 * Calm area+line chart with gridlines + tabular y-axis labels.
 * Used on dashboard for migration throughput trends.
 */
export function AreaChart({
  data,
  width = 720,
  height = 220,
  color = "var(--con-ink-1)",
  color2 = "var(--con-brand)",
  comparison,
}: AreaChartProps) {
  const rows = normalize(data);
  if (rows.length === 0) return null;
  const showB = comparison ?? rows.some((r) => r.b !== undefined);

  const padL = 36, padR = 8, padT = 16, padB = 28;
  const w = width - padL - padR;
  const h = height - padT - padB;
  const max = Math.max(...rows.flatMap((d) => [d.a || 0, d.b || 0]));
  const range = max - 0 || 1;
  const step = w / Math.max(1, rows.length - 1);
  const ptsA = rows.map((d, i) => [padL + i * step, padT + h - ((d.a - 0) / range) * h] as const);
  const ptsB = rows.map((d, i) => [padL + i * step, padT + h - (((d.b || 0) - 0) / range) * h] as const);
  const polyA = ptsA.map((p) => p.join(",")).join(" ");
  const polyB = ptsB.map((p) => p.join(",")).join(" ");
  const areaA = `${padL},${padT + h} ${polyA} ${padL + w},${padT + h}`;
  const ticks = 4;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="block overflow-visible">
      {/* Y grid */}
      {Array.from({ length: ticks + 1 }).map((_, i) => {
        const y = padT + (h / ticks) * i;
        const v = Math.round(max - (range / ticks) * i);
        return (
          <g key={i}>
            <line
              x1={padL}
              y1={y}
              x2={padL + w}
              y2={y}
              stroke="var(--con-line)"
              strokeDasharray={i === ticks ? "0" : "2 3"}
            />
            <text x={padL - 8} y={y + 4} fontSize="10" fill="var(--con-ink-4)" textAnchor="end" fontFamily="Geist Mono">
              {v}
            </text>
          </g>
        );
      })}
      {/* X labels — every ~8th */}
      {rows.map((d, i) =>
        i % Math.ceil(rows.length / 8) === 0 ? (
          <text
            key={i}
            x={padL + i * step}
            y={padT + h + 16}
            fontSize="10"
            fill="var(--con-ink-4)"
            textAnchor="middle"
            fontFamily="Geist Mono"
          >
            {d.label}
          </text>
        ) : null
      )}
      {/* Primary area + line */}
      <polygon points={areaA} fill={color} opacity="0.05" />
      <polyline
        points={polyA}
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {showB && (
        <polyline
          points={polyB}
          fill="none"
          stroke={color2}
          strokeWidth="1.5"
          strokeDasharray="3 3"
          strokeLinejoin="round"
        />
      )}
      {/* End dot */}
      {ptsA.length > 0 && (
        <circle cx={ptsA[ptsA.length - 1][0]} cy={ptsA[ptsA.length - 1][1]} r="3.5" fill={color} stroke="var(--con-surface)" strokeWidth="1.5" />
      )}
    </svg>
  );
}

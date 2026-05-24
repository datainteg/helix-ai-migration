interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutProps {
  data: DonutSegment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
  /** Legacy props — backward compat with original Donut */
  centerSub?: string;
}

/**
 * Quiet donut with a strong center number (mono) + small uppercase label.
 */
export function Donut({
  data,
  size = 140,
  thickness = 16,
  centerLabel,
  centerValue,
  centerSub,
}: DonutProps) {
  const total = data.reduce((a, b) => a + b.value, 0) || 1;
  const r = size / 2 - thickness / 2 - 1;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="relative inline-block" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--con-bg-2)" strokeWidth={thickness} />
        {data.map((d, i) => {
          const frac = d.value / total;
          const dash = frac * c;
          const seg = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={d.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              strokeLinecap="butt"
            />
          );
          offset += dash;
          return seg;
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {centerValue && (
          <div className="font-mono tabular-nums text-[22px] font-medium tracking-editorial">{centerValue}</div>
        )}
        {(centerLabel || centerSub) && (
          <div className="eyebrow text-[9px] mt-0.5">{centerLabel || centerSub}</div>
        )}
      </div>
    </div>
  );
}

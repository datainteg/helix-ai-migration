import { cn } from "@/lib/utils";
import { initials as initialsFn } from "@/lib/utils";

const palette = ["#1F2937", "#374151", "#4B5563", "#6B7280", "#0F766E", "#7C2D12", "#6B21A8", "#1E3A8A"];

interface AvatarProps {
  name: string;
  size?: "xs" | "sm" | "md" | "lg" | number;
  className?: string;
}

const sizeMap = { xs: 16, sm: 20, md: 24, lg: 32 };

export function Avatar({ name, size = "md", className }: AvatarProps) {
  const px = typeof size === "number" ? size : sizeMap[size];
  const init = initialsFn(name);
  const c = palette[(name.charCodeAt(0) || 0) % palette.length];
  return (
    <div
      className={cn(
        "rounded-full grid place-items-center text-white font-semibold flex-shrink-0 select-none",
        className
      )}
      style={{
        width: px,
        height: px,
        background: c,
        fontSize: Math.round(px * 0.4),
        letterSpacing: "0.02em",
      }}
    >
      {init}
    </div>
  );
}

export function AvatarGroup({ names, size = "sm", max = 4 }: { names: string[]; size?: AvatarProps["size"]; max?: number }) {
  const shown = names.slice(0, max);
  const extra = names.length - shown.length;
  return (
    <div className="flex -space-x-1.5">
      {shown.map((n) => (
        <div key={n} className="ring-2 ring-[var(--con-surface)] rounded-full">
          <Avatar name={n} size={size} />
        </div>
      ))}
      {extra > 0 && (
        <div
          className="ring-2 ring-[var(--con-surface)] rounded-full grid place-items-center font-mono text-ink-3 bg-app-2"
          style={{
            width: typeof size === "number" ? size : sizeMap[size as keyof typeof sizeMap],
            height: typeof size === "number" ? size : sizeMap[size as keyof typeof sizeMap],
            fontSize: 10.5,
          }}
        >
          +{extra}
        </div>
      )}
    </div>
  );
}

"use client";

/**
 * Quick-access tweaks drawer — opens from the Topbar.
 *
 * Same controls as the full /settings page, but inline. Changes write straight
 * to the Zustand store; `ThemeProvider` propagates to CSS vars on the next
 * render.
 */

import { useEffect, useState } from "react";
import { Moon, Sliders, Sun, X, Laptop, RotateCcw } from "lucide-react";

import { Density, ThemeMode, useTweaks } from "@/lib/theme-store";

const PRESET_COLORS = [
  "#4F46E5", // indigo (default)
  "#7C3AED", // violet
  "#0EA5E9", // sky
  "#15803D", // green
  "#D97757", // warm coral (figma)
  "#0F172A", // slate
];

const FONT_PRESETS = [11.5, 13.5, 15, 16];

interface TweaksPanelProps {
  open: boolean;
  onClose: () => void;
}

export function TweaksPanel({ open, onClose }: TweaksPanelProps) {
  const t = useTweaks();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!mounted || !open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        aria-label="Close tweaks"
        className="absolute inset-0 bg-black/30 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <aside className="relative w-[320px] max-w-full h-full bg-surface border-l border-hx shadow-lg overflow-y-auto">
        {/* Header */}
        <header className="sticky top-0 z-10 bg-surface border-b border-hx px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="h-4 w-4 text-ink-3" />
            <h2 className="text-[13.5px] font-semibold text-ink">Tweaks</h2>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={t.reset}
              title="Reset to defaults"
              className="grid place-items-center h-7 w-7 rounded-md text-ink-3 hover:bg-app-2"
            >
              <RotateCcw className="h-[14px] w-[14px]" />
            </button>
            <button
              aria-label="Close"
              onClick={onClose}
              className="grid place-items-center h-7 w-7 rounded-md text-ink-3 hover:bg-app-2"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="p-4 space-y-6">
          {/* Theme mode */}
          <Section label="Theme">
            <Segmented
              value={t.theme}
              options={[
                { value: "light", label: "Light", icon: Sun },
                { value: "dark", label: "Dark", icon: Moon },
                { value: "auto", label: "Auto", icon: Laptop },
              ]}
              onChange={(v) => t.setTheme(v as ThemeMode)}
            />
          </Section>

          {/* Density */}
          <Section label="Density">
            <Segmented
              value={t.density}
              options={[
                { value: "compact", label: "Compact" },
                { value: "regular", label: "Regular" },
                { value: "comfy", label: "Comfy" },
              ]}
              onChange={(v) => t.setDensity(v as Density)}
            />
          </Section>

          {/* Font size */}
          <Section label={`Font size — ${t.fontSizePx}px`}>
            <input
              type="range"
              min="10"
              max="18"
              step="0.5"
              value={t.fontSizePx}
              onChange={(e) => t.setFontSize(parseFloat(e.target.value))}
              className="w-full accent-[var(--con-brand)]"
            />
            <div className="flex gap-1 mt-2">
              {FONT_PRESETS.map((px) => (
                <button
                  key={px}
                  onClick={() => t.setFontSize(px)}
                  className={
                    "flex-1 h-7 rounded-md text-[11.5px] font-medium border " +
                    (Math.abs(t.fontSizePx - px) < 0.1
                      ? "border-con-brand text-con-brand bg-con-brand/5"
                      : "border-hx text-ink-3 hover:bg-app-2")
                  }
                >
                  {px}
                </button>
              ))}
            </div>
          </Section>

          {/* Surface tint */}
          <Section label="Surface tint">
            <Segmented
              value={t.surfaceTint}
              options={[
                { value: "warm", label: "Warm" },
                { value: "neutral", label: "Neutral" },
                { value: "cool", label: "Cool" },
              ]}
              onChange={(v) => t.setSurfaceTint(v as "warm" | "neutral" | "cool")}
            />
          </Section>

          {/* Primary color */}
          <Section label="Primary color">
            <div className="grid grid-cols-6 gap-2">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  aria-label={`Set primary color to ${color}`}
                  onClick={() => t.setPrimaryColor(color)}
                  className={
                    "aspect-square rounded-md border-2 " +
                    (t.primaryColor.toLowerCase() === color.toLowerCase()
                      ? "border-ink"
                      : "border-hx hover:border-hx-2")
                  }
                  style={{ background: color }}
                />
              ))}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <input
                type="color"
                value={t.primaryColor}
                onChange={(e) => t.setPrimaryColor(e.target.value)}
                className="h-7 w-10 rounded-md border border-hx bg-surface cursor-pointer"
              />
              <input
                type="text"
                value={t.primaryColor}
                onChange={(e) => t.setPrimaryColor(e.target.value)}
                className="flex-1 h-7 rounded-md border border-hx bg-surface px-2 text-[11.5px] font-mono focus-ring"
                spellCheck={false}
              />
            </div>
          </Section>

          {/* Footer note */}
          <p className="text-[10.5px] text-ink-4 leading-relaxed pt-2 border-t border-hx">
            Tweaks save to this browser via local storage. To sync across devices, save
            them in your profile from <a href="/settings" className="underline">Settings</a>.
          </p>
        </div>
      </aside>
    </div>
  );
}

// ── Small reusable controls ─────────────────────────────────────────

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="eyebrow mb-2">{label}</p>
      {children}
    </div>
  );
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string; icon?: React.ComponentType<{ className?: string }> }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex w-full p-0.5 rounded-md bg-app-2 border border-hx">
      {options.map((o) => {
        const active = o.value === value;
        const Icon = o.icon;
        return (
          <button
            key={String(o.value)}
            onClick={() => onChange(o.value)}
            className={
              "flex-1 inline-flex items-center justify-center gap-1.5 h-7 px-2 text-[11.5px] font-medium rounded transition-colors " +
              (active
                ? "bg-surface text-ink shadow-xs"
                : "text-ink-3 hover:text-ink-2")
            }
          >
            {Icon && <Icon className="h-[13px] w-[13px]" />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

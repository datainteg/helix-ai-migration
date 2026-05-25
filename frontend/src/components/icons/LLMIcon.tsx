"use client";

/**
 * LLMIcon — brand icon for an LLM provider (Anthropic, OpenAI, Google, ...).
 *
 * Mirrors `AppIcon` shape: real simple-icons paths when the brand is published,
 * letter fallback for OpenAI (trademark-restricted in simple-icons) and any
 * local/self-hosted runtime.
 */

import {
  siAnthropic,
  siGoogle,
  siGooglegemini,
  siDeepseek,
  siOpenrouter,
  siOllama,
  siMeta,
  siMistralai,
  siGooglecloud,
} from "simple-icons";

interface SimpleIcon {
  title: string;
  hex: string;
  path: string;
}

type Provider =
  | "anthropic" | "google" | "gemini" | "deepseek" | "openrouter" | "ollama"
  | "meta" | "mistralai" | "mistral" | "vertex"
  | "openai" | "local" | "bedrock" | "azure" | "custom";

const SI_MAP: Partial<Record<Provider, SimpleIcon>> = {
  anthropic:  siAnthropic,
  google:     siGoogle,
  gemini:     siGooglegemini,
  deepseek:   siDeepseek,
  openrouter: siOpenrouter,
  ollama:     siOllama,
  meta:       siMeta,
  mistralai:  siMistralai,
  mistral:    siMistralai,
  vertex:     siGooglecloud,
};

const FALLBACKS: Record<string, { letter: string; bg: string; fg?: string }> = {
  openai:  { letter: "O", bg: "#10A37F" },
  local:   { letter: "L", bg: "#71717A" },
  bedrock: { letter: "B", bg: "#FF9900" },           // AWS orange
  azure:   { letter: "A", bg: "#0078D4" },           // Azure blue
  custom:  { letter: "C", bg: "#52525B" },
  unknown: { letter: "?", bg: "#888" },
};

const ALIASES: Record<string, Provider> = {
  "anthropic-api":  "anthropic",
  claude:           "anthropic",
  "openai-api":     "openai",
  gpt:              "openai",
  "google-gemini":  "gemini",
  "vertex-ai":      "vertex",
  ollama:           "ollama",
  "aws-bedrock":    "bedrock",
  aws:              "bedrock",
  "azure-openai":   "azure",
  microsoft:        "azure",
};

function resolve(name: string): Provider | string {
  const k = name.trim().toLowerCase();
  return (ALIASES[k] as Provider | undefined) ?? (k as Provider);
}

interface LLMIconProps {
  provider: string;
  size?: number;
  bare?: boolean;
  className?: string;
}

export function LLMIcon({ provider, size = 18, bare, className }: LLMIconProps) {
  const key = resolve(provider);
  const brand = SI_MAP[key as Provider];

  if (brand) {
    const tileBg = `#${brand.hex}`;
    if (bare) {
      return (
        <svg
          viewBox="0 0 24 24"
          width={size}
          height={size}
          fill={tileBg}
          className={className}
          aria-label={brand.title}
          role="img"
        >
          <path d={brand.path} />
        </svg>
      );
    }
    return (
      <div
        className={"grid place-items-center rounded-[4px] flex-shrink-0 " + (className ?? "")}
        style={{ width: size, height: size, background: tileBg }}
        aria-label={brand.title}
      >
        <svg viewBox="0 0 24 24" width={size * 0.65} height={size * 0.65} fill="#FFFFFF" role="img">
          <path d={brand.path} />
        </svg>
      </div>
    );
  }

  const f = FALLBACKS[key] ?? FALLBACKS.unknown;
  return (
    <div
      className={"grid place-items-center rounded-[4px] font-mono font-bold flex-shrink-0 " + (className ?? "")}
      style={{
        width: size,
        height: size,
        background: f.bg,
        color: f.fg ?? "#FFFFFF",
        fontSize: size * 0.55,
        letterSpacing: "-0.03em",
      }}
      aria-label={provider}
    >
      {f.letter}
    </div>
  );
}

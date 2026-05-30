"use client";

/**
 * AgentIcon — role icon for a BMAD agent.
 *
 * BMAD agents are fictional personas (Mary the Analyst, John the PM, ...), so
 * we render a stable role-emoji-style glyph rather than a brand SVG. Backed by
 * react-icons (Material Design + Bootstrap subsets).
 */

import { IconType } from "react-icons";
import {
  MdAnalytics,
  MdManageAccounts,
  MdBrush,
  MdArchitecture,
  MdCode,
  MdEdit,
  MdSmartToy,
  MdPerson,
  MdAutoAwesome,
} from "react-icons/md";

type AgentKey =
  | "mary" | "analyst" | "bmad-agent-analyst"
  | "john" | "pm" | "bmad-agent-pm"
  | "sally" | "ux" | "bmad-agent-ux-designer"
  | "winston" | "architect" | "bmad-agent-architect"
  | "amelia" | "dev" | "bmad-agent-dev"
  | "paige" | "tech-writer" | "bmad-agent-tech-writer"
  | "assistant"
  | "system" | "human";

const ROLE: Record<AgentKey, { icon: IconType; bg: string; fg: string; label: string }> = {
  mary:                       { icon: MdAnalytics,      bg: "#EEF0FF", fg: "#4338CA", label: "Analyst" },
  analyst:                    { icon: MdAnalytics,      bg: "#EEF0FF", fg: "#4338CA", label: "Analyst" },
  "bmad-agent-analyst":       { icon: MdAnalytics,      bg: "#EEF0FF", fg: "#4338CA", label: "Analyst" },

  john:                       { icon: MdManageAccounts, bg: "#F5F3FF", fg: "#6D28D9", label: "PM" },
  pm:                         { icon: MdManageAccounts, bg: "#F5F3FF", fg: "#6D28D9", label: "PM" },
  "bmad-agent-pm":            { icon: MdManageAccounts, bg: "#F5F3FF", fg: "#6D28D9", label: "PM" },

  sally:                      { icon: MdBrush,          bg: "#FEF3C7", fg: "#B45309", label: "UX" },
  ux:                         { icon: MdBrush,          bg: "#FEF3C7", fg: "#B45309", label: "UX" },
  "bmad-agent-ux-designer":   { icon: MdBrush,          bg: "#FEF3C7", fg: "#B45309", label: "UX" },

  winston:                    { icon: MdArchitecture,   bg: "#DBEAFE", fg: "#1D4ED8", label: "Architect" },
  architect:                  { icon: MdArchitecture,   bg: "#DBEAFE", fg: "#1D4ED8", label: "Architect" },
  "bmad-agent-architect":     { icon: MdArchitecture,   bg: "#DBEAFE", fg: "#1D4ED8", label: "Architect" },

  amelia:                     { icon: MdCode,           bg: "#DCFCE7", fg: "#15803D", label: "Dev" },
  dev:                        { icon: MdCode,           bg: "#DCFCE7", fg: "#15803D", label: "Dev" },
  "bmad-agent-dev":           { icon: MdCode,           bg: "#DCFCE7", fg: "#15803D", label: "Dev" },

  paige:                      { icon: MdEdit,           bg: "#FEE2E2", fg: "#B91C1C", label: "Tech Writer" },
  "tech-writer":              { icon: MdEdit,           bg: "#FEE2E2", fg: "#B91C1C", label: "Tech Writer" },
  "bmad-agent-tech-writer":   { icon: MdEdit,           bg: "#FEE2E2", fg: "#B91C1C", label: "Tech Writer" },

  assistant:                  { icon: MdAutoAwesome,    bg: "#EEF0FF", fg: "#4F46E5", label: "Help Agent" },

  system:                     { icon: MdSmartToy,       bg: "#E4E4E7", fg: "#27272A", label: "System" },
  human:                      { icon: MdPerson,         bg: "#F4F4F5", fg: "#27272A", label: "Human" },
};

interface AgentIconProps {
  name: string;
  size?: number;
  className?: string;
}

export function AgentIcon({ name, size = 22, className }: AgentIconProps) {
  const k = name.trim().toLowerCase() as AgentKey;
  const role = ROLE[k] ?? ROLE.human;
  const Icon = role.icon;
  return (
    <div
      className={"grid place-items-center rounded-full flex-shrink-0 " + (className ?? "")}
      style={{ width: size, height: size, background: role.bg, color: role.fg }}
      aria-label={`${name} — ${role.label}`}
      title={role.label}
    >
      <Icon size={size * 0.6} />
    </div>
  );
}

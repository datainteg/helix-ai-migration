"use client";

import { Chip, type ChipTone } from "@/components/ui";
import type { StageStatus } from "@/lib/lifecycle/api";

// Lifecycle stage status → chip tone + label. Colour convention (per spec):
// approved/completed = green, under_review/edit_requested = yellow,
// rejected/failed = red, optional/skipped/not_started = gray, running = blue.
export const STAGE_STATUS_META: Record<StageStatus, { tone: ChipTone; label: string; pulse?: boolean }> = {
  not_started:    { tone: "zinc",  label: "Not started" },
  running:        { tone: "info",  label: "Running", pulse: true },
  generated:      { tone: "info",  label: "Generated" },
  under_review:   { tone: "warn",  label: "Under review" },
  edit_requested: { tone: "warn",  label: "Changes requested" },
  resubmitted:    { tone: "info",  label: "Resubmitted" },
  approved:       { tone: "ok",    label: "Approved" },
  rejected:       { tone: "err",   label: "Rejected" },
  completed:      { tone: "ok",    label: "Completed" },
  failed:         { tone: "err",   label: "Failed" },
  skipped:        { tone: "zinc",  label: "Skipped" },
};

export function StageStatusBadge({ status }: { status: StageStatus }) {
  const m = STAGE_STATUS_META[status] || { tone: "default" as ChipTone, label: status };
  return <Chip tone={m.tone} dot pulse={m.pulse}>{m.label}</Chip>;
}

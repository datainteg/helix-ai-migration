import { Chip } from "./Chip";

// Maps a freeform status string to a Chip tone + nicely-cased label.
// Pulse on "running" / "started" gives the operational feel.
const map: Record<string, { tone: "ok" | "warn" | "err" | "info" | "brand" | "default"; label?: string; pulse?: boolean }> = {
  // running / live
  running:      { tone: "info", label: "Running",   pulse: true },
  started:      { tone: "info", label: "Started",   pulse: true },
  in_progress:  { tone: "info", label: "In progress", pulse: true },
  active:       { tone: "info", label: "Active",    pulse: true },

  // waiting
  queued:       { tone: "default", label: "Queued" },
  pending:      { tone: "warn",    label: "Pending" },
  awaiting:     { tone: "warn",    label: "Awaiting" },
  awaiting_approval: { tone: "warn", label: "Awaiting" },

  // success
  completed:    { tone: "ok", label: "Completed" },
  passed:       { tone: "ok", label: "Passed" },
  success:      { tone: "ok", label: "Success" },
  healthy:      { tone: "ok", label: "Healthy" },
  done:         { tone: "ok", label: "Done" },
  approved:     { tone: "ok", label: "Approved" },

  // attention
  warning:      { tone: "warn", label: "Warning" },
  warn:         { tone: "warn", label: "Warning" },
  at_risk:      { tone: "warn", label: "At risk" },
  degraded:     { tone: "warn", label: "Degraded" },

  // failure
  failed:       { tone: "err", label: "Failed" },
  error:        { tone: "err", label: "Error" },
  critical:     { tone: "err", label: "Critical" },
  rejected:     { tone: "err", label: "Rejected" },
  down:         { tone: "err", label: "Down" },

  // neutral
  draft:        { tone: "default", label: "Draft" },
  idle:         { tone: "default", label: "Idle" },
  inactive:     { tone: "default", label: "Inactive" },
  paused:       { tone: "default", label: "Paused" },
  closed:       { tone: "default", label: "Closed" },
};

export function StatusBadge({ status, mono = false }: { status: string; mono?: boolean }) {
  const k = status.toLowerCase();
  const entry = map[k] ?? { tone: "default" as const };
  const label = entry.label || status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, " ");
  return (
    <Chip tone={entry.tone} dot pulse={!!entry.pulse} mono={mono}>
      {label}
    </Chip>
  );
}

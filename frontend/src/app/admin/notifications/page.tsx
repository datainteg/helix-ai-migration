"use client";

/**
 * /admin/notifications — notification rules + history.
 *
 * Rules: per-event toggle, threshold (for cost events), and channels
 * (in_app / email). History: all org notifications, searchable, with severity.
 * Rules writes are gated server-side by admin:llm:write.
 */

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Mail, Bell } from "lucide-react";

import { AdminShell } from "@/components/layout";
import { Card, Button, Chip, Tabs, ErrorBanner, LoadingState, EmptyState, SearchInput, StatusBadge, Table, THead, TBody, TR, TH, TD } from "@/components/ui";
import {
  fetchRules, upsertRule, fetchNotifications,
  type NotificationRule, type Notification, type Severity,
} from "@/lib/notifications/api";

const EVENT_LABELS: Record<string, { label: string; desc: string; hasThreshold?: boolean }> = {
  "cost.cap_approaching": { label: "Cost cap approaching", desc: "Org spend nears the cap.", hasThreshold: true },
  "cost.cap_breached": { label: "Cost cap breached", desc: "Org spend hit the cap." },
  "budget.cap_breached": { label: "Agent/project budget breached", desc: "A per-agent or per-project budget hit its cap." },
  "workflow.failed": { label: "Workflow failed", desc: "A migration / BMAD workflow failed." },
  "approval.pending": { label: "Approval pending", desc: "A step is awaiting human approval." },
};

// Map severity → a status string StatusBadge knows how to tone + label.
const SEV_STATUS: Record<Severity, string> = { info: "info", warning: "warning", error: "error", success: "success" };

type TabId = "rules" | "history";

export default function NotificationsAdminPage() {
  const [tab, setTab] = useState<TabId>("rules");
  const [rules, setRules] = useState<NotificationRule[]>([]);
  const [history, setHistory] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [r, h] = await Promise.all([
        fetchRules().catch(() => []),
        fetchNotifications(false, 200).catch(() => []),
      ]);
      setRules(r); setHistory(h); setErr("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const saveRule = async (rule: NotificationRule, patch: Partial<NotificationRule>) => {
    const next = { ...rule, ...patch };
    setRules((cur) => cur.map((r) => (r.event_type === rule.event_type ? next : r)));
    try {
      await upsertRule(rule.event_type, { enabled: next.enabled, threshold: next.threshold, channels: next.channels });
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
      void load(); // revert to server truth
    }
  };

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return history;
    return history.filter((n) => `${n.title} ${n.body ?? ""} ${n.type}`.toLowerCase().includes(s));
  }, [q, history]);

  return (
    <AdminShell
      title="Notifications"
      subtitle="Choose which events notify your team, the thresholds that trigger them, and the delivery channels."
      page="Notifications"
      actions={<Button variant="outline" onClick={() => void load()}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>}
    >
      {err && <ErrorBanner message={err} onDismiss={() => setErr("")} />}
      <Tabs tabs={[{ id: "rules", label: "Rules" }, { id: "history", label: "History", count: history.length }]} value={tab} onChange={(v) => setTab(v as TabId)} variant="pill" />

      {loading ? (
        <LoadingState label="Loading notifications…" />
      ) : tab === "rules" ? (
        <Card title="Event rules" description="A disabled event fires no notifications. Cost events use a threshold; channels are in-app and/or email." bodyClassName="p-0">
          <Table>
            <THead>
              <TR hover={false}><TH>Event</TH><TH>Enabled</TH><TH>Threshold</TH><TH>Channels</TH></TR>
            </THead>
            <TBody>
              {rules.map((r) => {
                const meta = EVENT_LABELS[r.event_type] ?? { label: r.event_type, desc: "" };
                const channels = (r.channels || "").split(",").filter(Boolean);
                return (
                  <TR key={r.event_type}>
                    <TD>
                      <div className="font-medium text-ink">{meta.label}</div>
                      <div className="text-[11.5px] text-ink-4 mt-0.5">{meta.desc}</div>
                    </TD>
                    <TD>
                      <button type="button" role="switch" aria-checked={r.enabled} onClick={() => saveRule(r, { enabled: !r.enabled })}
                        className={`relative h-5 w-9 rounded-full transition-colors ${r.enabled ? "bg-[var(--con-brand)]" : "bg-app-2 border border-hx-2"}`}>
                        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${r.enabled ? "left-[18px]" : "left-0.5"}`} />
                      </button>
                    </TD>
                    <TD>
                      {meta.hasThreshold ? (
                        <div className="flex items-center gap-1">
                          <input type="number" min="0" max="100" step="5"
                            value={r.threshold !== null && r.threshold !== undefined ? Math.round(r.threshold * 100) : 80}
                            onChange={(e) => saveRule(r, { threshold: Math.min(100, Math.max(0, Number(e.target.value))) / 100 })}
                            disabled={!r.enabled}
                            className="w-16 h-8 px-2 text-[12.5px] rounded-[6px] border border-hx bg-surface focus-ring font-mono disabled:opacity-50" />
                          <span className="text-[12px] text-ink-4">%</span>
                        </div>
                      ) : (
                        <span className="text-ink-4 text-[12px]">—</span>
                      )}
                    </TD>
                    <TD>
                      <div className="flex items-center gap-3">
                        <ChannelToggle icon={<Bell className="h-3.5 w-3.5" />} label="In-app" on={channels.includes("in_app")} disabled={!r.enabled}
                          onClick={() => saveRule(r, { channels: toggleCsv(r.channels, "in_app") })} />
                        <ChannelToggle icon={<Mail className="h-3.5 w-3.5" />} label="Email" on={channels.includes("email")} disabled={!r.enabled}
                          onClick={() => saveRule(r, { channels: toggleCsv(r.channels, "email") })} />
                      </div>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </Card>
      ) : (
        <Card title="History" description="All notifications for this organization." bodyClassName="p-0">
          <div className="p-3 border-b border-hx"><SearchInput value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notifications…" ariaLabel="Search notifications" /></div>
          {filtered.length === 0 ? (
            <div className="p-4"><EmptyState title="No notifications" description="Notifications appear here as events fire." /></div>
          ) : (
            <Table>
              <THead><TR hover={false}><TH>Severity</TH><TH>Title</TH><TH>Type</TH><TH>When</TH></TR></THead>
              <TBody>
                {filtered.map((n) => (
                  <TR key={n.id}>
                    <TD><StatusBadge status={SEV_STATUS[n.severity]} /></TD>
                    <TD><div className="font-medium text-ink">{n.title}</div>{n.body && <div className="text-[11.5px] text-ink-4 mt-0.5 max-w-[420px] truncate">{n.body}</div>}</TD>
                    <TD className="font-mono text-[11.5px] text-ink-3">{n.type}</TD>
                    <TD className="text-[11.5px] text-ink-4 whitespace-nowrap">{n.created_at ? new Date(n.created_at).toLocaleString() : "—"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </Card>
      )}
    </AdminShell>
  );
}

function toggleCsv(csv: string, key: string): string {
  const set = new Set((csv || "").split(",").filter(Boolean));
  if (set.has(key)) set.delete(key); else set.add(key);
  return Array.from(set).join(",") || "in_app";
}

function ChannelToggle({ icon, label, on, disabled, onClick }: { icon: React.ReactNode; label: string; on: boolean; disabled?: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-pressed={on}
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11.5px] border transition-colors disabled:opacity-50 ${on ? "border-[var(--con-brand)] bg-[var(--con-brand-soft)] text-[var(--con-brand)]" : "border-hx-2 bg-surface text-ink-4 hover:bg-app-2"}`}>
      {icon} {label}
    </button>
  );
}

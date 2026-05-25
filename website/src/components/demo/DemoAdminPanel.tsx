import { Cpu, Workflow, HeartPulse, ScrollText } from "lucide-react";
import { DemoShell } from "./DemoShell";
import { DEMO_LLM_PROVIDERS, DEMO_SYSTEM_HEALTH, DEMO_AUDIT_LOGS } from "@/data/demo-data";

const card = "bg-surface border border-zinc-200 rounded-xl shadow-soft p-5";

const AGENT_MODEL_MAP = [
  { agent: "Mary (BA)",        provider: "Anthropic", model: "claude-haiku-4-5"  },
  { agent: "John (PM)",        provider: "Anthropic", model: "claude-sonnet-4-6" },
  { agent: "Sally (UX)",       provider: "OpenAI",    model: "gpt-5.5"           },
  { agent: "Winston (Arch)",   provider: "Anthropic", model: "claude-opus-4-7"   },
  { agent: "Amelia (Dev)",     provider: "DeepSeek",  model: "deepseek-v4-pro"   },
  { agent: "Paige (Docs)",     provider: "OpenAI",    model: "gpt-5-mini"        },
];

const HEALTH_ITEMS: { key: keyof typeof DEMO_SYSTEM_HEALTH; label: string; metricLabel: string }[] = [
  { key: "backend",  label: "Backend",  metricLabel: "p95" },
  { key: "worker",   label: "Worker",   metricLabel: "queue depth" },
  { key: "temporal", label: "Temporal", metricLabel: "active workflows" },
  { key: "postgres", label: "Postgres", metricLabel: "connections" },
  { key: "redis",    label: "Redis",    metricLabel: "memory" },
];

function StatusDot({ status }: { status: string }) {
  const color =
    status === "ok" ? "bg-emerald-500" : status === "warn" ? "bg-amber-500" : "bg-rose-500";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} />;
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    active:   "bg-emerald-50 text-emerald-700",
    inactive: "bg-zinc-100 text-ink-3",
    ok:       "bg-emerald-50 text-emerald-700",
    warn:     "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${map[status] || "bg-zinc-100 text-ink-3"}`}>
      {status}
    </span>
  );
}

export function DemoAdminPanel() {
  return (
    <DemoShell title="Admin panel" description="Operator controls — LLM providers, agent routing, system health, and audit trail.">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* LLM Providers */}
        <div className={`${card} p-0 overflow-hidden`}>
          <Header icon={Cpu} title="LLM providers" sub={`${DEMO_LLM_PROVIDERS.length} configured`} />
          <div className="overflow-x-auto scroll-fade-x">
            <table className="w-full text-[12.5px]">
              <thead className="bg-surface-subtle text-ink-3">
                <tr>
                  <th className="text-left font-medium px-5 py-2.5">Name</th>
                  <th className="text-left font-medium px-3 py-2.5">Type</th>
                  <th className="text-left font-medium px-3 py-2.5">Default model</th>
                  <th className="text-left font-medium px-3 py-2.5">Status</th>
                  <th className="text-left font-medium px-3 py-2.5">Key</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_LLM_PROVIDERS.map((p) => (
                  <tr key={p.name} className="border-b border-zinc-200 last:border-0 hover:bg-surface-muted">
                    <td className="px-5 py-2.5 font-medium text-ink">{p.name}</td>
                    <td className="px-3 py-2.5 font-mono text-ink-3">{p.provider_type}</td>
                    <td className="px-3 py-2.5 font-mono text-ink-2">{p.default_model}</td>
                    <td className="px-3 py-2.5"><StatusPill status={p.status} /></td>
                    <td className="px-3 py-2.5 font-mono text-ink-4">{p.masked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Agent model mapping */}
        <div className={`${card} p-0 overflow-hidden`}>
          <Header icon={Workflow} title="Agent model mapping" sub="6 BMAD agents" />
          <div className="overflow-x-auto scroll-fade-x">
            <table className="w-full text-[12.5px]">
              <thead className="bg-surface-subtle text-ink-3">
                <tr>
                  <th className="text-left font-medium px-5 py-2.5">Agent</th>
                  <th className="text-left font-medium px-3 py-2.5">Provider</th>
                  <th className="text-left font-medium px-3 py-2.5">Model</th>
                </tr>
              </thead>
              <tbody>
                {AGENT_MODEL_MAP.map((m) => (
                  <tr key={m.agent} className="border-b border-zinc-200 last:border-0 hover:bg-surface-muted">
                    <td className="px-5 py-2.5 font-medium text-ink">{m.agent}</td>
                    <td className="px-3 py-2.5 text-ink-3">{m.provider}</td>
                    <td className="px-3 py-2.5 font-mono text-ink-2">{m.model}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* System health */}
        <div className={`${card} p-0 overflow-hidden`}>
          <Header icon={HeartPulse} title="System health" sub="last 5 minutes" />
          <ul className="divide-y divide-zinc-200">
            {HEALTH_ITEMS.map((row) => {
              const h = DEMO_SYSTEM_HEALTH[row.key] as Record<string, string | number>;
              const metricKey = Object.keys(h).find((k) => k !== "status" && k !== "uptime") || "";
              const metricVal = metricKey ? h[metricKey] : "—";
              return (
                <li key={row.key} className="px-5 py-3 flex items-center gap-3">
                  <StatusDot status={String(h.status)} />
                  <div className="flex-1">
                    <div className="text-[13px] font-medium text-ink">{row.label}</div>
                    <div className="text-[11px] text-ink-4 font-mono mt-0.5">
                      uptime {h.uptime} · {row.metricLabel} {String(metricVal)}
                    </div>
                  </div>
                  <StatusPill status={String(h.status)} />
                </li>
              );
            })}
          </ul>
        </div>

        {/* Audit logs */}
        <div className={`${card} p-0 overflow-hidden`}>
          <Header icon={ScrollText} title="Audit logs" sub="HMAC-signed chain" />
          <div className="overflow-x-auto scroll-fade-x">
            <table className="w-full text-[12.5px]">
              <thead className="bg-surface-subtle text-ink-3">
                <tr>
                  <th className="text-left font-medium px-5 py-2.5">Timestamp</th>
                  <th className="text-left font-medium px-3 py-2.5">Actor</th>
                  <th className="text-left font-medium px-3 py-2.5">Action</th>
                  <th className="text-left font-medium px-3 py-2.5">Entity</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_AUDIT_LOGS.map((a, i) => (
                  <tr key={i} className="border-b border-zinc-200 last:border-0 hover:bg-surface-muted">
                    <td className="px-5 py-2.5 font-mono text-ink-3 text-[11.5px]">{a.ts}</td>
                    <td className="px-3 py-2.5 text-ink">{a.actor}</td>
                    <td className="px-3 py-2.5 font-mono text-ink-2">{a.action}</td>
                    <td className="px-3 py-2.5 text-ink-3 truncate max-w-[180px]">{a.entity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </DemoShell>
  );
}

function Header({ icon: Icon, title, sub }: { icon: any; title: string; sub: string }) {
  return (
    <div className="px-5 py-3 border-b border-zinc-200 flex items-center gap-3">
      <div className="h-7 w-7 rounded-md bg-brand-50 text-brand-600 grid place-items-center">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <h3 className="text-[14px] font-semibold text-ink leading-tight">{title}</h3>
        <p className="text-[11px] text-ink-4 mt-0.5">{sub}</p>
      </div>
    </div>
  );
}

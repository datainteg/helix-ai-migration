import { SectionHeader } from "@/components/layout/SectionHeader";
import { Architecture } from "@/components/landing/Architecture";
import { Agents } from "@/components/landing/Agents";
import { CTA } from "@/components/landing/CTA";

const SERVICES = [
  { name: "frontend",  role: "Next.js 14 operator UI (App Router)",            port: "3000" },
  { name: "backend",   role: "FastAPI · 18 routers · async SQLAlchemy",        port: "8000" },
  { name: "worker",    role: "Temporal worker · BMAD pipeline executor",       port: "—" },
  { name: "postgres",  role: "Primary store · projects, runs, audit chain",    port: "5432" },
  { name: "redis",     role: "Cache · streaming bus · rate limit",             port: "6379" },
  { name: "temporal",  role: "Durable workflow engine + UI",                   port: "7233 / 8233" },
];

export function ArchitecturePage() {
  return (
    <>
      <section className="py-16 md:py-20 container-tight">
        <SectionHeader
          eyebrow="System map"
          title="Architecture"
          description="How the brain, the worker, the API, and your data plane plug together."
        />
      </section>

      <Architecture />
      <Agents />

      <section className="py-16 md:py-24 container-tight">
        <SectionHeader
          eyebrow="Service topology"
          title="The five services that make up Helix."
          description="Each runs as its own container in the bundled docker-compose."
        />
        <div className="mt-10 bg-surface border border-zinc-200 rounded-xl shadow-soft p-6">
          <SystemSvg />
        </div>

        <div className="mt-8 bg-surface border border-zinc-200 rounded-xl shadow-soft overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-zinc-50 border-b border-zinc-200">
              <tr>
                <th className="px-5 py-3 text-[11px] eyebrow text-ink-4">Service</th>
                <th className="px-5 py-3 text-[11px] eyebrow text-ink-4">Role</th>
                <th className="px-5 py-3 text-[11px] eyebrow text-ink-4">Port</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200">
              {SERVICES.map((s) => (
                <tr key={s.name}>
                  <td className="px-5 py-3.5 font-mono text-[13px] text-ink">{s.name}</td>
                  <td className="px-5 py-3.5 text-[13px] text-ink-3">{s.role}</td>
                  <td className="px-5 py-3.5 font-mono text-[12.5px] text-ink-4">{s.port}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <CTA />
    </>
  );
}

function SystemSvg() {
  return (
    <svg
      viewBox="0 0 820 220"
      className="w-full h-auto"
      role="img"
      aria-label="Frontend to Backend to Worker to BMAD to LLM provider data flow"
    >
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717A" />
        </marker>
      </defs>

      <SvgBox x={10}  y={70}  w={140} h={80}  label="Frontend"      sub="Next.js · 3000" color="#4F46E5" />
      <SvgBox x={180} y={70}  w={140} h={80}  label="Backend"       sub="FastAPI · 8000" color="#06B6D4" />
      <SvgBox x={350} y={70}  w={140} h={80}  label="Worker"        sub="Temporal"        color="#15803D" />
      <SvgBox x={520} y={70}  w={140} h={80}  label="BMAD Brain"    sub="6 agents · 13 nodes" color="#B45309" />
      <SvgBox x={690} y={70}  w={120} h={80}  label="LLM Provider"  sub="10 supported"   color="#7C3AED" />

      <line x1={150} y1={110} x2={180} y2={110} stroke="#71717A" strokeWidth={1.6} markerEnd="url(#arrow)" />
      <line x1={320} y1={110} x2={350} y2={110} stroke="#71717A" strokeWidth={1.6} markerEnd="url(#arrow)" />
      <line x1={490} y1={110} x2={520} y2={110} stroke="#71717A" strokeWidth={1.6} markerEnd="url(#arrow)" />
      <line x1={660} y1={110} x2={690} y2={110} stroke="#71717A" strokeWidth={1.6} markerEnd="url(#arrow)" />

      <text x={410} y={30} textAnchor="middle" fontFamily="JetBrains Mono, ui-monospace, monospace" fontSize={10} fill="#71717A" letterSpacing="0.12em">
        REQUEST FLOW
      </text>
      <line x1={20} y1={42} x2={800} y2={42} stroke="#E4E4E7" strokeWidth={1} strokeDasharray="3 4" />

      <text x={410} y={200} textAnchor="middle" fontFamily="JetBrains Mono, ui-monospace, monospace" fontSize={10} fill="#71717A" letterSpacing="0.12em">
        ARTIFACTS &amp; STATE PERSIST TO POSTGRES + REDIS
      </text>
    </svg>
  );
}

function SvgBox({
  x, y, w, h, label, sub, color,
}: {
  x: number; y: number; w: number; h: number; label: string; sub: string; color: string;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={10} ry={10} fill="#FAFAF9" stroke={color} strokeWidth={1.4} />
      <rect x={x} y={y} width={4} height={h} rx={2} ry={2} fill={color} />
      <text x={x + w / 2} y={y + 34} textAnchor="middle" fontSize={14} fontWeight={600} fill="#0A0A0A">
        {label}
      </text>
      <text x={x + w / 2} y={y + 54} textAnchor="middle" fontSize={11} fill="#52525B" fontFamily="JetBrains Mono, ui-monospace, monospace">
        {sub}
      </text>
    </g>
  );
}

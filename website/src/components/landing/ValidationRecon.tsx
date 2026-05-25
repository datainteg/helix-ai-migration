import { ShieldCheck, GitCompareArrows, Check } from "lucide-react";

import { SectionHeader } from "@/components/layout/SectionHeader";

const VALIDATION_BULLETS = [
  "Row counts",
  "Null checks",
  "Duplicates",
  "Schema parity",
  "Business rules",
];

const RECON_BULLETS = [
  "Source vs target parity",
  "Rolling history",
  "Metadata only — no row-level data leaves",
  "Release gates with multi-approver sign-off",
];

export function ValidationRecon() {
  return (
    <section className="py-16 md:py-24 container-tight">
      <SectionHeader
        eyebrow="Validation + reconciliation"
        title="Prove the migration before you cut over."
        description="Eight built-in rules + signed recon reports. Trust the gate, not the gut."
      />
      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-5">
        <SplitCard
          icon={<ShieldCheck className="h-5 w-5" />}
          accent="#15803D"
          eyebrow="Validation engine"
          hero="8 built-in rules"
          subtitle="Run on every load, surface coverage trends per sprint."
          bullets={VALIDATION_BULLETS}
        />
        <SplitCard
          icon={<GitCompareArrows className="h-5 w-5" />}
          accent="#4F46E5"
          eyebrow="Reconciliation"
          hero="Metadata only"
          subtitle="Source vs target parity stays in your environment — Helix never stores rows."
          bullets={RECON_BULLETS}
        />
      </div>
    </section>
  );
}

function SplitCard({
  icon,
  accent,
  eyebrow,
  hero,
  subtitle,
  bullets,
}: {
  icon: React.ReactNode;
  accent: string;
  eyebrow: string;
  hero: string;
  subtitle: string;
  bullets: string[];
}) {
  return (
    <div className="bg-surface border border-zinc-200 rounded-xl shadow-soft p-7">
      <div className="flex items-center gap-3">
        <div
          className="h-10 w-10 rounded-lg grid place-items-center text-white"
          style={{ background: accent }}
        >
          {icon}
        </div>
        <div className="eyebrow" style={{ color: accent }}>
          {eyebrow}
        </div>
      </div>
      <div className="mt-5 text-[28px] md:text-[32px] font-semibold tracking-tight text-ink leading-tight">
        {hero}
      </div>
      <p className="mt-2 text-[13px] text-ink-3 leading-relaxed">{subtitle}</p>
      <ul className="mt-5 space-y-2">
        {bullets.map((b) => (
          <li key={b} className="flex items-start gap-2.5 text-[13px] text-ink-2">
            <span
              className="mt-[3px] h-4 w-4 rounded-full grid place-items-center shrink-0"
              style={{ background: `${accent}1a`, color: accent }}
            >
              <Check className="h-2.5 w-2.5" />
            </span>
            {b}
          </li>
        ))}
      </ul>
    </div>
  );
}

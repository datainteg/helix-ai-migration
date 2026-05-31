"use client";

import type { MigrationStage } from "@/lib/lifecycle/api";
import { LifecycleStageCard } from "./LifecycleStageCard";

interface Props {
  stages: MigrationStage[];
  projectKey: string;
  currentStageKey?: string | null;
}

// Vertical stage timeline: a connecting rail with one card per stage.
export function LifecycleTimeline({ stages, projectKey, currentStageKey }: Props) {
  return (
    <ol className="relative space-y-2.5 pl-5">
      <span className="absolute left-[7px] top-2 bottom-2 w-px bg-hx" aria-hidden />
      {stages.map((s) => (
        <li key={s.id} className="relative">
          <span
            className="absolute -left-[18px] top-4 h-2.5 w-2.5 rounded-full border-2 border-app bg-hx-2"
            aria-hidden
          />
          <LifecycleStageCard stage={s} projectKey={projectKey} isCurrent={s.stage_key === currentStageKey} />
        </li>
      ))}
    </ol>
  );
}

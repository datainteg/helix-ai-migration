"use client";

import { cn } from "@/lib/utils";
import { Chip } from "@/components/ui";
import type { MigrationArtifactVersion } from "@/lib/lifecycle/api";

interface Props {
  versions: MigrationArtifactVersion[];          // newest first
  currentVersionId: string | null;
  selectedVersionId: string | null;
  onSelect: (v: MigrationArtifactVersion) => void;
}

// Left-rail version list for the review/compare pages.
export function ArtifactVersionList({ versions, currentVersionId, selectedVersionId, onSelect }: Props) {
  if (versions.length === 0) return <p className="text-[12px] text-ink-3">No versions yet.</p>;
  return (
    <ul className="space-y-1">
      {versions.map((v) => {
        const isCurrent = v.id === currentVersionId;
        const isSel = v.id === selectedVersionId;
        return (
          <li key={v.id}>
            <button
              onClick={() => onSelect(v)}
              className={cn(
                "w-full rounded-md border px-2.5 py-2 text-left transition-colors",
                isSel ? "border-helix-400 bg-app-2" : "border-hx hover:bg-app-2",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[13px] font-medium text-ink-1">v{v.version_number}</span>
                <div className="flex items-center gap-1">
                  {isCurrent && <Chip tone="ok" mono>current</Chip>}
                  <Chip tone={v.created_by_type === "agent" ? "brand" : "zinc"} mono>{v.created_by_type}</Chip>
                </div>
              </div>
              {v.change_summary && <p className="mt-1 truncate text-[11.5px] text-ink-3">{v.change_summary}</p>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

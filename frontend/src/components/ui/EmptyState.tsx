import React from "react";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-4 gap-2">
      {icon && (
        <div className="grid place-items-center h-9 w-9 rounded-lg bg-app-2 text-ink-3 mb-2">
          {icon}
        </div>
      )}
      <div className="text-[13.5px] font-medium text-ink">{title}</div>
      {description && (
        <div className="text-[12px] text-ink-3 max-w-sm">{description}</div>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

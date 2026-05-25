import { AlertCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
  className?: string;
}

export function ErrorBanner({ message, onDismiss, className }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "flex items-start gap-3 px-4 py-2.5 rounded-[10px] border bg-[var(--con-err-soft)] border-[#FCA5A5] text-err",
        className
      )}
    >
      <AlertCircle className="h-4 w-4 mt-px flex-shrink-0" aria-hidden />
      <div className="flex-1 text-[12.5px] leading-snug">{message}</div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="grid place-items-center h-5 w-5 rounded hover:bg-black/5"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { Button, ErrorBanner } from "@/components/ui";

/**
 * Route-level error boundary.
 * Next 14 wraps every route in this client component; uncaught render errors
 * are caught here instead of crashing the whole shell. The `reset` prop
 * re-renders the segment from scratch.
 */
export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to the browser console so devs/operators can grep.
    // Replace with a real telemetry sink when one is wired.
    // eslint-disable-next-line no-console
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 px-4 py-12">
      <div className="max-w-xl w-full">
        <ErrorBanner
          message={
            error.message ||
            "Something went wrong while rendering this page. You can try again, or head back to the dashboard."
          }
        />
        {error.digest && (
          <div className="mt-2 text-[11px] font-mono text-ink-4">digest: {error.digest}</div>
        )}
      </div>
      <div className="flex gap-2">
        <Button variant="primary" onClick={() => reset()}>
          Try again
        </Button>
        <a
          href="/dashboard"
          className="inline-flex items-center justify-center h-8 px-3 text-[12.5px] rounded-[8px] border border-hx-2 bg-surface text-ink-2 hover:bg-app-2"
        >
          Back to dashboard
        </a>
      </div>
    </div>
  );
}

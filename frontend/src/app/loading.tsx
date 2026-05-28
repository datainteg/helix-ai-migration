import { LoadingState } from "@/components/ui";

/**
 * Route-level loading boundary.
 * Next 14 renders this between navigation events while the route segment
 * is still loading. Keeps the shell from going blank on slow networks.
 */
export default function RootLoading() {
  return (
    <div className="min-h-[60vh] grid place-items-center">
      <LoadingState label="Loading…" />
    </div>
  );
}

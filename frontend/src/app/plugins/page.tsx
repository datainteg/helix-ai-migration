"use client";

/**
 * /plugins — placeholder.
 *
 * Plugin marketplace isn't built yet; this stub keeps the route navigable
 * so existing sidebar links don't 404. Replace with the real plugin catalog
 * once the extension SDK is published.
 */

import Link from "next/link";
import { Puzzle } from "lucide-react";
import { AppShell } from "@/components/layout";
import { Button, Card, EmptyState } from "@/components/ui";

export default function PluginsPage() {
  return (
    <AppShell
      eyebrow="EXTENSIONS"
      title="Plugins"
      description="Extend Helix with first-party and community plugins."
      crumbs={[{ label: "Plugins" }]}
    >
      <Card>
        <EmptyState
          icon={<Puzzle className="h-5 w-5" />}
          title="Plugin marketplace is coming soon"
          description="Pluggable connectors, custom validators, and recon engines will be installable from here once the extension SDK ships."
          action={
            <Link href="/dashboard">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
          }
        />
      </Card>
    </AppShell>
  );
}

"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/query-client";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/components/ThemeProvider";
import { CrumbLabelProvider } from "@/lib/breadcrumbs";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <CrumbLabelProvider>{children}</CrumbLabelProvider>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

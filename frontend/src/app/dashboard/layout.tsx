import type { ReactNode } from "react";
export const metadata = { title: "Dashboard · Helix" };
export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

import type { ReactNode } from "react";
export const metadata = { title: "New Project · Helix" };
export default function Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AppState {
  activeProjectId: string | null;
  sidebarCollapsed: boolean;
  setActiveProject: (id: string | null) => void;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      activeProjectId: null,
      sidebarCollapsed: false,
      setActiveProject: (id) => set({ activeProjectId: id }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    { name: "helix-app" }
  )
);

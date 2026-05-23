"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/use-api";
import type { ProjectCreate, ProjectResponse, RequirementCreate, RequirementResponse } from "@/lib/api-types";

export const projectKeys = {
  all: ["projects"] as const,
  detail: (id: string) => ["projects", id] as const,
  requirements: (id: string) => ["projects", id, "requirements"] as const,
};

export function useProjects() {
  const api = useApi();
  return useQuery({
    queryKey: projectKeys.all,
    queryFn: () => api.get<ProjectResponse[]>("/api/v1/projects"),
  });
}

export function useProject(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => api.get<ProjectResponse>(`/api/v1/projects/${id}`),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) => api.post<ProjectResponse>("/api/v1/projects", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectKeys.all }),
  });
}

export function useRequirements(projectId: string) {
  const api = useApi();
  return useQuery({
    queryKey: projectKeys.requirements(projectId),
    queryFn: () => api.get<RequirementResponse[]>(`/api/v1/projects/${projectId}/requirements`),
    enabled: !!projectId,
  });
}

export function useCreateRequirement(projectId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RequirementCreate) =>
      api.post<RequirementResponse>(`/api/v1/projects/${projectId}/requirements`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: projectKeys.requirements(projectId) }),
  });
}

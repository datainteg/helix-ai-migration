"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/use-api";
import type {
  LLMProviderCreate, LLMProviderResponse, AgentMappingCreate,
  AgentMappingResponse, CatalogueEntry, TestConnectionResponse,
} from "@/lib/api-types";

export const llmKeys = {
  providers: ["llm-providers"] as const,
  catalogue: ["llm-providers", "catalogue"] as const,
  mappings: ["llm-agent-mappings"] as const,
};

export function useLLMProviders() {
  const api = useApi();
  return useQuery({
    queryKey: llmKeys.providers,
    queryFn: () => api.get<LLMProviderResponse[]>("/api/v1/llm-providers"),
  });
}

export function useLLMCatalogue() {
  const api = useApi();
  return useQuery({
    queryKey: llmKeys.catalogue,
    queryFn: () =>
      api.get<CatalogueEntry[]>("/api/v1/llm-providers/catalogue").then((entries) => {
        const map: Record<string, CatalogueEntry> = {};
        entries.forEach((e) => { map[e.provider_type] = e; });
        return map;
      }),
    staleTime: Infinity,
  });
}

export function useCreateLLMProvider() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: LLMProviderCreate) => api.post<LLMProviderResponse>("/api/v1/llm-providers", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: llmKeys.providers }),
  });
}

export function useTestLLMProvider() {
  const api = useApi();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<TestConnectionResponse>(`/api/v1/llm-providers/${id}/test`),
  });
}

export function useAgentMappings() {
  const api = useApi();
  return useQuery({
    queryKey: llmKeys.mappings,
    queryFn: () => api.get<AgentMappingResponse[]>("/api/v1/llm-agent-mappings"),
  });
}

export function useCreateAgentMapping() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentMappingCreate) =>
      api.post<AgentMappingResponse>("/api/v1/llm-agent-mappings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: llmKeys.mappings }),
  });
}

// Server-state queries for hub + profil (TanStack Query, sekcja 8).
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Campaign, Chronicle, Hero, LlmSettings } from "@/lib/types";

export function useHeroes() {
  return useQuery({
    queryKey: ["heroes"],
    queryFn: () => apiFetch<{ heroes: Hero[] }>("/heroes"),
    select: (d) => d.heroes,
  });
}

export function useCampaigns() {
  return useQuery({
    queryKey: ["campaigns"],
    queryFn: () => apiFetch<{ campaigns: Campaign[] }>("/campaigns"),
    select: (d) => d.campaigns,
  });
}

export function useLlmSettings(userId: number | undefined) {
  return useQuery({
    queryKey: ["llm-settings", userId],
    enabled: !!userId,
    queryFn: () => apiFetch<LlmSettings>(`/users/${userId}/llm-settings`),
  });
}

export function useChronicle(userId: number | undefined) {
  // Aggregate lifetime stats come from the hero roster; the per-hero chronicle
  // endpoint is per-character. For the profil tiles we derive from heroes.
  return useQuery({
    queryKey: ["chronicle", userId],
    enabled: false, // placeholder — profil derives tiles from /heroes for now
    queryFn: () => apiFetch<Chronicle>(`/users/${userId}/chronicle`),
  });
}

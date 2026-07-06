import { QueryClient } from "@tanstack/react-query";

// Server-state defaults. Per-query refetchInterval opts in to polling
// (turns ~3–5s, combat 1.5s) — patrz frontend_design.md sekcja 8.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

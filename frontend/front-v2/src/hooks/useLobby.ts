import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  declineLobby,
  generateInviteLink,
  getLobby,
  inviteByUsername,
  kickPlayer,
  startLobby,
} from "@/lib/multiplayer";

// FE15 (#1264) — lobby: polling 5 s (F-71). Query jest źródłem realtime dla lobby;
// gra (rundy/czat) ma własny poller do Zustand.
export function useLobby(campaignId: number | undefined) {
  return useQuery({
    queryKey: ["mp-lobby", campaignId],
    enabled: !!campaignId,
    queryFn: () => getLobby(campaignId!),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });
}

export function useInviteByUsername(campaignId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (username: string) => inviteByUsername(campaignId, username),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mp-lobby", campaignId] }),
  });
}

export function useInviteLink(campaignId: number) {
  return useMutation({
    mutationFn: () => generateInviteLink(campaignId),
  });
}

export function useKickPlayer(campaignId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (targetUserId: number) => kickPlayer(campaignId, targetUserId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["mp-lobby", campaignId] }),
  });
}

export function useStartLobby(campaignId: number) {
  return useMutation({ mutationFn: () => startLobby(campaignId) });
}

export function useDeclineLobby(campaignId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => declineLobby(campaignId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}

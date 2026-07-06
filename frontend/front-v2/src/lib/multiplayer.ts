// FE15 (#1264) — warstwa API multiplayer: lobby, rundy, party-chat, whispery.
// Zachowania portowane ze starego frontend/front/js/multiplayer_ui.js.
// Źródło prawdy endpointów: frontend_design.md §7 (F-71) + backend api/multiplayer.py.
import { apiFetch } from "@/lib/api";

// ── Lobby ────────────────────────────────────────────────────────────────────

export interface LobbyMember {
  user_id: number;
  username: string;
  display_name: string;
  role: string; // owner | player | spectator
  status: string; // accepted | pending | declined
  character_id: number | null;
  absence_warnings: number;
  autopilot_consent: boolean;
}

export interface LobbyState {
  campaign_id: number;
  title: string;
  system_id: string;
  round_timer_minutes: number;
  round_timer_hours: number;
  max_players: number;
  host_user_id: number;
  lobby_status: string; // open | started | ...
  is_host: boolean;
  members: LobbyMember[];
  accepted_count: number;
  vote_kick_suggested: boolean;
}

export function getLobby(campaignId: number) {
  return apiFetch<LobbyState>(`/multiplayer/campaigns/${campaignId}/lobby`);
}

export interface CreateLobbyReq {
  title: string;
  round_timer_minutes?: number;
  max_players?: number;
  template_id?: number;
}

export function createLobby(body: CreateLobbyReq) {
  return apiFetch<{ campaign_id: number }>("/multiplayer/campaigns", {
    method: "POST",
    body,
  });
}

export function startLobby(campaignId: number) {
  return apiFetch<unknown>(`/multiplayer/campaigns/${campaignId}/start`, {
    method: "POST",
  });
}

export function inviteByUsername(campaignId: number, username: string) {
  return apiFetch<unknown>(
    `/multiplayer/campaigns/${campaignId}/invite/username`,
    { method: "POST", body: { username } },
  );
}

export function generateInviteLink(campaignId: number) {
  return apiFetch<{ token: string; expires_at: string }>(
    `/multiplayer/campaigns/${campaignId}/invite-link`,
    { method: "POST" },
  );
}

export function kickPlayer(campaignId: number, targetUserId: number) {
  return apiFetch<unknown>(
    `/multiplayer/campaigns/${campaignId}/players/${targetUserId}`,
    { method: "DELETE" },
  );
}

export function declineLobby(campaignId: number) {
  return apiFetch<unknown>(`/multiplayer/campaigns/${campaignId}/decline`, {
    method: "POST",
  });
}

export function joinViaToken(token: string) {
  return apiFetch<{ campaign_id: number; title: string }>(
    `/multiplayer/join/${token}`,
  );
}

export function updateRoundTimer(campaignId: number, minutes: number) {
  return apiFetch<unknown>(`/multiplayer/campaigns/${campaignId}/timer`, {
    method: "PATCH",
    body: { round_timer_minutes: minutes },
  });
}

// ── Rundy ────────────────────────────────────────────────────────────────────

export type RoundStatusName = "none" | "collecting" | "narrating" | "done";

export interface RoundStatus {
  round_id: number;
  round_number: number;
  status: RoundStatusName;
  deadline: string | null;
  submitted_count: number;
  total_players: number;
  my_submitted: boolean;
  my_action: string | null;
  host_note?: string | null;
}

export interface RoundAction {
  character_name: string;
  action_text: string;
}

export interface RoundNarration {
  round_id: number;
  round_number?: number;
  actions: RoundAction[];
  narrative: string;
  my_note?: string | null;
}

export function getRoundStatus(campaignId: number) {
  return apiFetch<RoundStatus>(`/campaigns/${campaignId}/round/status`);
}

export function getRoundNarration(campaignId: number) {
  return apiFetch<RoundNarration>(`/campaigns/${campaignId}/round/narration`);
}

export function getRoundsHistory(campaignId: number) {
  return apiFetch<{ rounds: RoundNarration[] }>(
    `/campaigns/${campaignId}/rounds/history`,
  );
}

export interface SubmitRoundResult {
  round_id: number;
  status: RoundStatusName;
  submitted?: number;
  total?: number;
}

export function submitRoundAction(
  campaignId: number,
  body: { action_text: string; character_id: number | null; character_name: string },
) {
  return apiFetch<SubmitRoundResult>(`/campaigns/${campaignId}/round/submit`, {
    method: "POST",
    body,
  });
}

// ── Party chat / whispery ─────────────────────────────────────────────────────

export interface ChatMessage {
  id: number;
  user_id: number;
  character_name: string;
  message: string;
  created_at: string;
  is_mine: boolean;
  whisper_to: string | null;
}

export function getPartyChat(campaignId: number, sinceId: number) {
  return apiFetch<{ messages: ChatMessage[] }>(
    `/multiplayer/campaigns/${campaignId}/chat?since_id=${sinceId}`,
  );
}

export function postPartyChat(
  campaignId: number,
  body: { message: string; character_name: string; whisper_to: string | null },
) {
  return apiFetch<unknown>(`/multiplayer/campaigns/${campaignId}/chat`, {
    method: "POST",
    body,
  });
}

// `/whisper <postać> <tekst>` → { whisperTo, message }. Zwykła wiadomość → whisperTo=null.
export function parseWhisper(raw: string): { whisperTo: string | null; message: string } {
  const m = raw.trim().match(/^\/whisper\s+(\S+)\s+(.+)$/i);
  if (m) return { whisperTo: m[1], message: m[2] };
  return { whisperTo: null, message: raw.trim() };
}

// Odlicz do deadline'u → skrót „1h 20m" / „05:12" (mm:ss gdy < 1h).
export function formatCountdown(deadline: string | null): string {
  if (!deadline) return "—:—:—";
  const diff = new Date(deadline).getTime() - Date.now();
  if (diff <= 0) return "Koniec";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function formatMinutes(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const rem = min % 60;
  return rem > 0 ? `${h} h ${rem} min` : `${h} h`;
}

/**
 * Notification preferences + Telegram easy-click linking (#602 N1 · #883).
 * Thin typed wrappers over the backend notify-prefs / telegram endpoints.
 */
import { apiFetch } from "./api";

export interface NotifyPrefs {
  web_push_enabled: boolean;
  telegram_connected: boolean;
  email: string | null;
  channel_order: string;
}

export interface TelegramLink {
  token: string;
  deep_link: string | null;
  bot_username: string | null;
  configured: boolean;
}

export interface TelegramStatus {
  connected: boolean;
  configured: boolean;
}

export const getNotifyPrefs = () => apiFetch<NotifyPrefs>("/users/notify-prefs");

export const putNotifyPrefs = (p: Partial<Pick<NotifyPrefs, "web_push_enabled" | "email" | "channel_order">>) =>
  apiFetch<NotifyPrefs>("/users/notify-prefs", { method: "PUT", body: p });

export const createTelegramLink = () =>
  apiFetch<TelegramLink>("/users/telegram/link-token", { method: "POST" });

export const getTelegramStatus = () => apiFetch<TelegramStatus>("/users/telegram/status");

export const unlinkTelegram = () =>
  apiFetch<{ connected: boolean }>("/users/telegram", { method: "DELETE" });

/** Rough mobile check — decides deep-link (tap) vs QR (scan from desktop). */
export function isMobile(): boolean {
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}

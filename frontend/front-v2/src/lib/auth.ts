// Token + user persistence (localStorage). Keys match the legacy front so a
// session started in either UI interoperates during the migration window.
import type { CurrentUser } from "@/store/appStore";

const ACCESS_KEY = "aigm_access_token";
const REFRESH_KEY = "aigm_refresh_token";
const USER_KEY = "aigm_user_v2";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_KEY, token);
}

export function storeSession(
  access: string,
  refresh: string | undefined,
  user: CurrentUser,
): void {
  localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function readStoredUser(): CurrentUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CurrentUser;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  // Also clear legacy keys so a stale token can't shadow the fresh one.
  localStorage.removeItem("token");
}

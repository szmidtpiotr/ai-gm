// Thin fetch wrapper for the AI-GM backend. Bearer auth from localStorage,
// one silent refresh on 401, typed JSON responses, Polish-friendly errors.
import {
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  clearSession,
} from "./auth";

const API_BASE = "/api";

export class APIError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.detail = detail;
  }
}

interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip attaching the bearer token (login/register/reset endpoints). */
  anon?: boolean;
  /** Internal: prevents infinite refresh recursion. */
  _retried?: boolean;
}

function extractMessage(status: number, payload: unknown): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const d = (payload as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: unknown }).message);
    }
  }
  return `Błąd ${status}`;
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { access_token?: string };
    if (data.access_token) {
      setAccessToken(data.access_token);
      return true;
    }
  } catch {
    /* network error — treat as failed refresh */
  }
  return false;
}

/** Wyrzuca na logowanie po nieudanym odświeżeniu sesji (raz, bez pętli). */
function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const base = import.meta.env.BASE_URL || "/"; // "/graj/"
  const loginPath = `${base}login`.replace(/\/{2,}/g, "/");
  if (window.location.pathname === loginPath) return;
  window.location.replace(loginPath);
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: ApiOptions = {},
): Promise<T> {
  const { body, anon, _retried, headers, ...rest } = opts;
  const h: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string>),
  };
  if (body !== undefined) h["Content-Type"] = "application/json";
  if (!anon) {
    const token = getAccessToken();
    if (token) h["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: h,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Silent one-shot refresh on an expired access token.
  if (res.status === 401 && !anon && !_retried) {
    const ok = await tryRefresh();
    if (ok) return apiFetch<T>(path, { ...opts, _retried: true });
    // Sesja wygasła — bez tego przekierowania ekran zostaje na trasie
    // chronionej i pokazuje generyczny błąd ("Nie udało się wczytać…").
    clearSession();
    redirectToLogin();
  }

  if (res.status === 204) return undefined as T;

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    throw new APIError(res.status, extractMessage(res.status, payload), payload);
  }
  return payload as T;
}

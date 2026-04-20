const TOKEN_KEY = "aigm_admin_token";
const BASE_URL_KEY = "aigm_admin_baseurl";

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || "").trim().replace(/\/+$/, "");
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getBaseUrl() {
  return localStorage.getItem(BASE_URL_KEY) || "";
}

export function isConnected() {
  return Boolean(getToken() && getBaseUrl());
}

export async function connect(baseUrl, token) {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const normalizedToken = String(token || "").trim();

  if (!normalizedBaseUrl || !normalizedToken) {
    throw new Error("Base URL and token are required.");
  }

  const response = await fetch(`${normalizedBaseUrl}/api/admin/verify`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${normalizedToken}`,
    },
  });

  let body = null;
  try {
    body = await response.json();
  } catch (_error) {
    body = null;
  }

  if (!response.ok || !body || body.ok !== true) {
    throw new Error("Token verification failed.");
  }

  localStorage.setItem(BASE_URL_KEY, normalizedBaseUrl);
  localStorage.setItem(TOKEN_KEY, normalizedToken);
  return true;
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(BASE_URL_KEY);
  window.location.reload();
}

export async function autoConnect() {
  const baseUrl = getBaseUrl();
  const token = getToken();
  if (!baseUrl || !token) {
    return false;
  }

  try {
    await connect(baseUrl, token);
    return true;
  } catch (_error) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(BASE_URL_KEY);
    return false;
  }
}

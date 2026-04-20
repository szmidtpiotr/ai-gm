const TOKEN_KEY = "aigm_admin_token";
const BASE_URL_KEY = "aigm_admin_baseurl";

export class APIError extends Error {
  constructor(status, body, message = "API request failed") {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.body = body;
  }
}

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || "").replace(/\/+$/, "");
}

function buildUrl(path) {
  const baseUrl = normalizeBaseUrl(localStorage.getItem(BASE_URL_KEY));
  if (!baseUrl) {
    throw new APIError(0, { error: "Missing API base URL" }, "Not connected");
  }

  if (String(path).startsWith("http://") || String(path).startsWith("https://")) {
    return path;
  }

  const normalizedPath = String(path || "").startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}

export async function adminFetch(path, options = {}) {
  const startedAt = Date.now();
  const url = buildUrl(path);
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response;
  let responseBody = null;

  try {
    response = await fetch(url, {
      ...options,
      headers,
    });

    const contentType = response.headers.get("Content-Type") || "";
    if (contentType.includes("application/json")) {
      responseBody = await response.json();
    } else {
      const textBody = await response.text();
      responseBody = textBody ? { raw: textBody } : null;
    }

    if (!response.ok) {
      throw new APIError(response.status, responseBody);
    }

    return responseBody;
  } catch (error) {
    if (!(error instanceof APIError)) {
      throw new APIError(0, { error: error.message || "Network error" }, "Network request failed");
    }
    throw error;
  } finally {
    window.dispatchEvent(
      new CustomEvent("admin-fetch", {
        detail: {
          path,
          url,
          method: (options.method || "GET").toUpperCase(),
          ok: response ? response.ok : false,
          status: response ? response.status : 0,
          startedAt,
          endedAt: Date.now(),
        },
      }),
    );
  }
}

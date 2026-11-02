const API_URL = import.meta.env.VITE_API_URL;

const REFRESH_KEY = 'chess.refreshToken';

// The access token lives only in memory; the refresh token survives reloads.
let accessToken = null;
let refreshInFlight = null;
let onSessionExpired = () => {};

export class ApiError extends Error {
  constructor(status, detail) {
    super(describeDetail(detail) || `Request failed (${status}).`);
    this.status = status;
    this.detail = detail;
  }
}

function describeDetail(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg?.replace(/^Value error, /, '') ?? String(item)).join(' ');
  }
  return String(detail);
}

function readRefreshToken() {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function setTokens(tokens) {
  accessToken = tokens?.access_token ?? null;
  try {
    if (tokens?.refresh_token) localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    // Storage may be unavailable (private mode); the session then ends on reload.
  }
}

export function hasRefreshToken() {
  return Boolean(readRefreshToken());
}

export function getRefreshToken() {
  return readRefreshToken();
}

export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

function buildUrl(path, query) {
  const url = `${API_URL}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') params.set(key, value);
  });
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function send(path, { method = 'GET', body, query, signal, headers = {} }) {
  const response = await fetch(buildUrl(path, query), {
    method,
    signal,
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
  });
  return response;
}

export async function refreshSession() {
  const refreshToken = readRefreshToken();
  if (!refreshToken) return false;

  // Concurrent 401s share one refresh, because refresh tokens are single-use.
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(buildUrl('/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        setTokens(null);
        return false;
      }
      setTokens(await response.json());
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

/**
 * Call the API and return parsed JSON (null for 204).
 * Attaches the bearer token, retries once after refreshing on 401, and throws
 * ApiError({ status, detail }) for any non-2xx response.
 */
export async function api(path, options = {}) {
  let response = await send(path, options);

  if (response.status === 401 && !path.startsWith('/auth/') && (await refreshSession())) {
    response = await send(path, options);
  }

  if (response.status === 401 && !path.startsWith('/auth/')) {
    onSessionExpired();
  }

  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = null;
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

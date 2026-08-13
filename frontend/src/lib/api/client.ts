/**
 * Axios instance with automatic Bearer token injection and proactive token refresh.
 *
 * Strategy: check the JWT expiry in the REQUEST interceptor (before sending).
 * If the token expires within 60 seconds, refresh proactively — zero 401s for
 * normal session renewal. The RESPONSE interceptor is a fallback for edge cases
 * (server clock skew, revoked tokens).
 *
 * Token lifecycle:
 *   - access_token (15 min) — in-memory store + localStorage (updated on refresh)
 *   - refresh_token (7 days) — localStorage only
 *   - On near-expiry: transparently refreshes before the request fires
 *   - On refresh failure: clears auth + redirects to /login (or / for a
 *     superadmin session — see loginPathFor() below). /login is a school's
 *     own sign-in page and shows no usable form at all off that school's
 *     subdomain (see routes/login/+page.svelte) — sending a superadmin
 *     there on session expiry was a real dead end, not just the wrong page.
 *
 * PUBLIC AUTH ENDPOINTS (login, superadmin-login, refresh, forgot-password,
 * verify-otp, reset-password, accept-invite, invite-info) are excluded from
 * both interceptors entirely — see isPublicAuthPath(). A 401 from one of
 * these is a real answer (wrong password, bad OTP), not a sign the caller's
 * own session expired; before this exclusion existed, the response
 * interceptor treated every 401 as "maybe the token expired," tried to
 * refresh (always fails — there's no session to refresh during a login
 * attempt), and redirected away — silently swallowing the real error
 * (a login form's "Invalid credentials" message never rendered) and, worse,
 * bouncing straight into the redirect loop this same file's superadmin
 * fix exists to prevent.
 */
import axios, { type InternalAxiosRequestConfig } from 'axios';
import { get } from 'svelte/store';
import { auth } from '$lib/stores/auth';

export const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

// ── Public auth endpoints — never subject to the refresh/redirect dance ──────
// A 401 from one of these is a real, meaningful answer (wrong password,
// bad/expired OTP, expired invite token) — not a sign the caller's session
// died. Before this exclusion existed, the response interceptor treated
// every 401 as "maybe the access token expired," tried to refresh (which
// always fails here since there's no session to refresh), and redirected to
// a login page — silently swallowing the real error and, for a login
// attempt itself, meaning a wrong password never even reached the form's
// own error handling. Matched by suffix since `client`'s baseURL is
// '/api' and callers pass the path only (e.g. '/auth/login').
const _PUBLIC_AUTH_PATHS = [
  '/auth/login', '/auth/superadmin-login', '/auth/refresh',
  '/auth/forgot-password', '/auth/verify-otp', '/auth/reset-password',
  '/auth/accept-invite', '/auth/invite-info', // invite-info/{token} — prefix match
];
function isPublicAuthPath(url: string | undefined): boolean {
  if (!url) return false;
  const path = url.split('?')[0];
  return _PUBLIC_AUTH_PATHS.some(p => path === p || path.endsWith(p) || path.includes(`${p}/`));
}

// ── JWT expiry helper ────────────────────────────────────────────────────────

function parseJwtExpiry(token: string): number | null {
  try {
    // JWT payload is base64url encoded (- → +, _ → /)
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(b64));
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

// ── Shared refresh logic (deduplicates concurrent calls) ─────────────────────

let refreshPromise: Promise<string | null> | null = null;

/** Where to send the user after a session dies. /login only ever renders a
 * usable form on a school's own subdomain/custom domain (routes/login/
 * +page.svelte) — a superadmin has no school at all, so must always land
 * back on / instead. Read the flag before clearAuth() wipes it. */
function loginPathFor(): string {
  return get(auth).user?.is_superadmin ? '/' : '/login';
}

function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  const rt = localStorage.getItem('refresh_token');
  if (!rt) {
    const path = loginPathFor();
    auth.clearAuth();
    window.location.href = path;
    return Promise.resolve(null);
  }

  refreshPromise = axios
    .post('/api/auth/refresh', { refresh_token: rt })
    .then(({ data }) => {
      const newToken = data.access_token as string;
      auth.setToken(newToken); // also persists to localStorage
      localStorage.setItem('refresh_token', data.refresh_token);
      return newToken;
    })
    .catch(() => {
      const path = loginPathFor();
      auth.clearAuth();
      window.location.href = path;
      return null;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

// ── Request interceptor: attach token, refresh proactively if near expiry ────

client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (isPublicAuthPath(config.url)) return config;

  let token = get(auth).accessToken;
  if (!token) return config;

  const expiry = parseJwtExpiry(token);
  // Refresh proactively if the token expires within the next 60 seconds.
  // This eliminates 401s on page refresh after idle periods.
  if (expiry !== null && expiry - Date.now() < 60_000) {
    const refreshed = await refreshAccessToken();
    token = refreshed ?? token;
  }

  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: fallback for unexpected 401s ────────────────────────
// Handles revoked tokens, server clock skew, or edge cases the request
// interceptor didn't catch (e.g., token invalidated server-side mid-session).

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

client.interceptors.response.use(
  res => res,
  async error => {
    const original = error.config as RetryConfig;
    if (error.response?.status !== 401 || original._retry || isPublicAuthPath(original?.url)) {
      return Promise.reject(error);
    }
    original._retry = true;

    const newToken = await refreshAccessToken();
    if (!newToken) return Promise.reject(error);

    original.headers.Authorization = `Bearer ${newToken}`;
    return client(original);
  }
);

export { client as api };
export default client;

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
 *   - On refresh failure: clears auth + redirects to /login
 */
import axios, { type InternalAxiosRequestConfig } from 'axios';
import { get } from 'svelte/store';
import { auth } from '$lib/stores/auth';

export const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

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

function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  const rt = localStorage.getItem('refresh_token');
  if (!rt) {
    auth.clearAuth();
    window.location.href = '/login';
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
      auth.clearAuth();
      window.location.href = '/login';
      return null;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
}

// ── Request interceptor: attach token, refresh proactively if near expiry ────

client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
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
    if (error.response?.status !== 401 || original._retry) {
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

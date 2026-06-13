/**
 * Axios instance with automatic Bearer token injection and silent token refresh.
 *
 * Token lifecycle:
 *   - access_token (15 min) stored in memory (auth store)
 *   - refresh_token (7 days) stored in localStorage
 *   - On 401: transparently refreshes, retries original request once
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

// ── Request interceptor: attach current access token ─────────────────────────

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = get(auth).accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Response interceptor: silent 401 recovery ────────────────────────────────

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let isRefreshing = false;
let pendingQueue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = [];

function drainQueue(error: unknown, token: string | null) {
  pendingQueue.forEach(p => (token ? p.resolve(token) : p.reject(error)));
  pendingQueue = [];
}

client.interceptors.response.use(
  res => res,
  async error => {
    const original = error.config as RetryConfig;
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    original._retry = true;

    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then(token => {
        original.headers.Authorization = `Bearer ${token}`;
        return client(original);
      });
    }

    isRefreshing = true;
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
      auth.clearAuth();
      window.location.href = '/login';
      return Promise.reject(error);
    }

    try {
      const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken });
      const { access_token, refresh_token: newRefresh } = data;
      auth.setToken(access_token);
      localStorage.setItem('refresh_token', newRefresh);
      drainQueue(null, access_token);
      original.headers.Authorization = `Bearer ${access_token}`;
      return client(original);
    } catch (refreshError) {
      drainQueue(refreshError, null);
      auth.clearAuth();
      window.location.href = '/login';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export default client;

import { writable, derived, get } from 'svelte/store';
import { browser } from '$app/environment';

export interface CurrentUser {
  id: string;
  email: string | null;
  phone: string | null;
  school_id: string | null;
  staff_member_id: string | null;
  student_id: string | null;
  guardian_id: string | null;
  is_superadmin: boolean;
  login_type: 'EMAIL' | 'PHONE' | 'ADMISSION_ID';
  display_name: string | null;
}

interface AuthState {
  user: CurrentUser | null;
  accessToken: string | null;
  schoolId: string | null;
  offlineSessionStartedAt: string | null;
}

// Pre-hydrate from localStorage so the first request already carries the Bearer token.
// Without this, TanStack Query fires before onMount runs and every page load starts
// with a 401 → silent refresh cycle even when the stored token is still valid.
const EMPTY: AuthState = {
  user: null,
  accessToken: browser ? localStorage.getItem('access_token') : null,
  schoolId: null,
  offlineSessionStartedAt: browser ? localStorage.getItem('offline_session_started_at') : null,
};

function createAuth() {
  const store = writable<AuthState>(EMPTY);
  const { subscribe, set, update } = store;

  return {
    subscribe,

    /** Called after successful login or token refresh. */
    setAuth(user: CurrentUser, accessToken: string, refreshToken: string) {
      const offlineSessionStartedAt = new Date().toISOString();
      set({ user, accessToken, schoolId: user.school_id, offlineSessionStartedAt });
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      localStorage.setItem('offline_session_started_at', offlineSessionStartedAt);
      // Persisted (not just kept on the in-memory `user` object) so
      // lib/api/client.ts can tell a superadmin session apart from a
      // regular one synchronously on a fresh page load — `user` itself
      // isn't populated until /auth/me resolves in +layout.svelte's
      // onMount, which is too late if a token-refresh failure fires first.
      localStorage.setItem('is_superadmin', user.is_superadmin ? '1' : '0');
    },

    /** Called after silent access-token refresh — no new user object needed. */
    setToken(accessToken: string) {
      update(s => ({ ...s, accessToken }));
      localStorage.setItem('access_token', accessToken);
    },

    /** Called when user's /me data is loaded (e.g. on app startup). */
    setUser(user: CurrentUser) {
      update(s => ({ ...s, user, schoolId: user.school_id }));
    },

    clearAuth() {
      // Don't reset to EMPTY — EMPTY.accessToken captured the old token at module load time.
      // Set a clean null state so no stale token leaks through after sign-out.
      set({ user: null, accessToken: null, schoolId: null, offlineSessionStartedAt: null });
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('offline_session_started_at');
      localStorage.removeItem('is_superadmin');
    },

    /** Restore access token from memory (set by server-side or prior session). */
    hydrate(accessToken: string) {
      const osa = localStorage.getItem('offline_session_started_at');
      update(s => ({ ...s, accessToken, offlineSessionStartedAt: osa }));
    },

    get offlineSessionStartedAt(): string | null {
      return get(store).offlineSessionStartedAt;
    },
  };
}

export const auth = createAuth();
export const isAuthenticated = derived(auth, $a => !!$a.accessToken);
export const currentUser = derived(auth, $a => $a.user);
export const schoolId = derived(auth, $a => $a.schoolId);

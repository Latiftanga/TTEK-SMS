import { writable, derived, get } from 'svelte/store';

export interface CurrentUser {
  id: string;
  email: string | null;
  phone: string | null;
  school_id: string | null;
  staff_member_id: string | null;
  student_id: string | null;
  is_superadmin: boolean;
  login_type: 'EMAIL' | 'PHONE' | 'ADMISSION_ID';
}

interface AuthState {
  user: CurrentUser | null;
  accessToken: string | null;
  schoolId: string | null;
  offlineSessionStartedAt: string | null;
}

const EMPTY: AuthState = {
  user: null,
  accessToken: null,
  schoolId: null,
  offlineSessionStartedAt: null,
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
      localStorage.setItem('refresh_token', refreshToken);
      localStorage.setItem('offline_session_started_at', offlineSessionStartedAt);
    },

    /** Called after silent access-token refresh — no new user object needed. */
    setToken(accessToken: string) {
      update(s => ({ ...s, accessToken }));
    },

    /** Called when user's /me data is loaded (e.g. on app startup). */
    setUser(user: CurrentUser) {
      update(s => ({ ...s, user, schoolId: user.school_id }));
    },

    clearAuth() {
      set(EMPTY);
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('offline_session_started_at');
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

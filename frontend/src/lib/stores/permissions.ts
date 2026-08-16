import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

export type DashboardView = 'staff' | 'admin' | 'approver' | 'finance' | null;

const STORAGE_KEY = 'user_view';

const _view = writable<DashboardView>(
  browser ? (localStorage.getItem(STORAGE_KEY) as DashboardView) : null
);

export const userRole = {
  subscribe: _view.subscribe,
  set: (view: DashboardView) => {
    _view.set(view);
    if (browser) {
      if (view) localStorage.setItem(STORAGE_KEY, view);
      else localStorage.removeItem(STORAGE_KEY);
    }
  },
  reset: () => {
    _view.set(null);
    if (browser) localStorage.removeItem(STORAGE_KEY);
  },
};

export const isSchoolAdmin = derived(_view, $v => $v === 'admin');
export const isApprover   = derived(_view, $v => $v === 'approver');
export const isFinance     = derived(_view, $v => $v === 'finance');

// Independent capability signals, computed regardless of which `view` is
// primary — these are what sidebar nav gating (teachingOnly/
// classTeacherOnly/housemasterOnly) actually checks now, not the `view`
// string, so a staff member who holds several responsibilities at once
// (e.g. Class Teacher + Housemaster) doesn't lose nav items for the ones
// that didn't "win" the primary view.
function persistedBoolean(key: string) {
  const store = writable<boolean>(browser ? localStorage.getItem(key) === 'true' : false);
  return {
    subscribe: store.subscribe,
    set: (value: boolean) => {
      store.set(value);
      if (browser) localStorage.setItem(key, String(value));
    },
  };
}

export const isClassTeacher   = persistedBoolean('user_is_class_teacher');
export const isSubjectTeacher = persistedBoolean('user_is_subject_teacher');
export const isHousemaster    = persistedBoolean('user_is_housemaster');

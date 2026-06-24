import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

export type DashboardView = 'teacher' | 'admin' | 'approver' | 'finance' | 'housemaster' | null;

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

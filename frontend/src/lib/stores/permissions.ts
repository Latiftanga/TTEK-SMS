import { writable, derived } from 'svelte/store';

export type DashboardView = 'teacher' | 'admin' | 'hod' | 'finance' | null;

const _view = writable<DashboardView>(null);

export const userRole = {
  subscribe: _view.subscribe,
  set: (view: DashboardView) => _view.set(view),
  reset: () => _view.set(null),
};

export const isSchoolAdmin = derived(_view, $v => $v === 'admin');
export const isHod        = derived(_view, $v => $v === 'hod');
export const isFinance    = derived(_view, $v => $v === 'finance');

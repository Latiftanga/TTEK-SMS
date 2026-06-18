import { writable } from 'svelte/store';

export type ToastKind = 'success' | 'error' | 'info' | 'warning';

export interface ToastItem {
  id: string;
  kind: ToastKind;
  message: string;
}

function createToastStore() {
  const { subscribe, update } = writable<ToastItem[]>([]);

  function push(kind: ToastKind, message: string, ms = 4000) {
    const id = Math.random().toString(36).slice(2);
    update(ts => [...ts.slice(-2), { id, kind, message }]);
    if (ms > 0) setTimeout(() => dismiss(id), ms);
  }

  function dismiss(id: string) {
    update(ts => ts.filter(t => t.id !== id));
  }

  return {
    subscribe,
    success: (msg: string, ms?: number) => push('success', msg, ms),
    error:   (msg: string, ms?: number) => push('error',   msg, ms),
    info:    (msg: string, ms?: number) => push('info',    msg, ms),
    warning: (msg: string, ms?: number) => push('warning', msg, ms),
    dismiss,
  };
}

export const toast = createToastStore();

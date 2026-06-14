import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type ThemeMode = 'light' | 'dark' | 'system';

let mediaUnlisten: (() => void) | null = null;

function applyTheme(mode: ThemeMode) {
  if (!browser) return;
  const root = document.documentElement;
  if (mediaUnlisten) { mediaUnlisten(); mediaUnlisten = null; }

  if (mode === 'dark') {
    root.classList.add('dark');
    root.classList.remove('light');
  } else if (mode === 'light') {
    root.classList.remove('dark');
    root.classList.add('light');
  } else {
    // System: follow prefers-color-scheme and watch for changes
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const sync = (e: { matches: boolean }) => {
      root.classList.toggle('dark', e.matches);
      root.classList.remove('light');
    };
    sync(mq);
    const handler = (e: MediaQueryListEvent) => sync(e);
    mq.addEventListener('change', handler);
    mediaUnlisten = () => mq.removeEventListener('change', handler);
  }
}

function createTheme() {
  const initial: ThemeMode = browser
    ? ((localStorage.getItem('theme') as ThemeMode) ?? 'system')
    : 'system';

  const { subscribe, set } = writable<ThemeMode>(initial);

  return {
    subscribe,
    set(mode: ThemeMode) {
      if (browser) localStorage.setItem('theme', mode);
      applyTheme(mode);
      set(mode);
    },
    /** Call once on app mount to apply stored preference. */
    init() {
      const stored = browser
        ? ((localStorage.getItem('theme') as ThemeMode) ?? 'system')
        : 'system';
      applyTheme(stored);
      set(stored);
    },
  };
}

export const theme = createTheme();

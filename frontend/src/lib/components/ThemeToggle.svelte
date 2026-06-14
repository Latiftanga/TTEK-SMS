<script lang="ts">
  import { theme, type ThemeMode } from '$lib/stores/theme';

  const cycle: ThemeMode[] = ['light', 'dark', 'system'];

  const icons: Record<ThemeMode, string> = {
    light:  `<path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364-.707.707M6.343 17.657l-.707.707m12.728 0-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/>`,
    dark:   `<path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z"/>`,
    system: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 0 1-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0 1 15 18.257V17.25m6-12V15a2.25 2.25 0 0 1-2.25 2.25H5.25A2.25 2.25 0 0 1 3 15V5.25m18 0A2.25 2.25 0 0 0 18.75 3H5.25A2.25 2.25 0 0 0 3 5.25m18 0H3"/>`,
  };

  const labels: Record<ThemeMode, string> = {
    light: 'Light', dark: 'Dark', system: 'Auto',
  };

  function cycle_theme() {
    const idx = cycle.indexOf($theme);
    theme.set(cycle[(idx + 1) % cycle.length]);
  }
</script>

<button
  onclick={cycle_theme}
  title="{labels[$theme]} mode — click to switch"
  aria-label="{labels[$theme]} mode"
  class="relative flex h-8 w-8 items-center justify-center rounded-xl
         text-[var(--fg-muted)] ring-1 ring-[var(--border)]
         hover:bg-[var(--hover)] hover:text-[var(--fg)] hover:ring-[var(--border-strong)]
         active:scale-95"
  style="background: var(--card); box-shadow: var(--shadow-xs);"
>
  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75"
       viewBox="0 0 24 24" aria-hidden="true">
    {@html icons[$theme]}
  </svg>
</button>

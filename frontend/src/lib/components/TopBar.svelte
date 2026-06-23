<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import ThemeToggle from './ThemeToggle.svelte';
  import { school } from '$lib/stores/school';
  import { getCurrentYear } from '$lib/api/academic';

  interface Props { toggleSidebar: () => void; }
  const { toggleSidebar }: Props = $props();

  const today = new Date().toLocaleDateString('en-GH', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });

  const schoolInitials = $derived.by(() => {
    const n = $school?.name ?? 'S';
    const words = n.split(' ').filter((w: string) => w.length > 1);
    return (words.length >= 2 ? words[0][0] + words[1][0] : n.slice(0, 2)).toUpperCase();
  });

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const currentTerm = $derived(($yearQ.data?.terms ?? []).find(t => t.is_current));

  // Label shown in the chip: "Term 1 · 2025/2026" or "No active term · 2025/2026" or "No academic year"
  const termLabel = $derived.by(() => {
    if ($yearQ.isPending) return null;
    if (!$yearQ.data) return { term: 'No academic year', year: '' };
    return {
      term: currentTerm?.name ?? 'No active term',
      year: $yearQ.data.name,
    };
  });
</script>

<header class="sticky top-0 z-40 flex h-14 items-center gap-3
               bg-[var(--card)] px-4 lg:px-6"
        style="padding-top: env(safe-area-inset-top); box-shadow: 0 1px 0 var(--border), 0 4px 16px rgba(0,0,0,0.06);">

  <!-- Mobile: hamburger -->
  <button onclick={toggleSidebar} aria-label="Open navigation"
    class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--fg-muted)]
           transition hover:bg-[var(--hover)] hover:text-[var(--fg)] lg:hidden">
    <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
    </svg>
  </button>

  <!-- Mobile: school identity -->
  <div class="flex min-w-0 items-center gap-2 lg:hidden">
    {#if $school?.logoUrl}
      <img src={$school.logoUrl} alt={$school.name}
           class="h-7 w-7 shrink-0 rounded-lg object-contain ring-1 ring-[var(--border)]" />
    {:else}
      <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold text-white"
           style="background-color: var(--brand)">
        {schoolInitials}
      </div>
    {/if}
    <p class="truncate text-sm font-bold text-[var(--fg)] max-w-[110px]" title={$school?.name}>
      {$school?.shortName ?? $school?.name ?? 'My School'}
    </p>
  </div>

  <!-- Academic year + term chip — all screen sizes -->
  {#if termLabel}
    <a href="/admin/academic"
       class="flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border)]
              px-2.5 py-1.5 transition hover:border-[var(--brand)]/40 hover:bg-[var(--hover)]">
      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2"
           viewBox="0 0 24 24" style="color: var(--brand)">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25
             2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0
             0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
      </svg>
      <span class="text-xs font-semibold text-[var(--fg)]">{termLabel.term}</span>
      {#if termLabel.year}
        <span class="hidden text-[var(--fg-subtle)] sm:inline">·</span>
        <span class="hidden text-xs text-[var(--fg-muted)] sm:inline">{termLabel.year}</span>
      {/if}
    </a>
  {/if}

  <!-- Desktop: date -->
  <span class="hidden text-sm text-[var(--fg-muted)] lg:block">{today}</span>

  <!-- Right: theme toggle -->
  <div class="ml-auto flex items-center">
    <ThemeToggle />
  </div>
</header>

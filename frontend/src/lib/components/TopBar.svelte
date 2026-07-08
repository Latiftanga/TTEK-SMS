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

  const daysLeft = $derived(
    currentTerm
      ? Math.ceil((new Date(currentTerm.end_date).getTime() - Date.now()) / 86_400_000)
      : null
  );

  const termUrgent = $derived(daysLeft !== null && daysLeft <= 14);
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

  <!-- ── Academic context pills ───────────────────────────────────────────────── -->
  {#if !$yearQ.isPending}
    {#if !$yearQ.data}
      <!-- No year set — amber CTA -->
      <a href="/admin/academic/years"
         class="flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold
                transition hover:opacity-80
                border-amber-300 bg-amber-50 text-amber-700
                dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-400">
        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z"/>
        </svg>
        Set up academic year
      </a>

    {:else if !currentTerm}
      <!-- Year OK, no active term -->
      <div class="flex shrink-0 items-center gap-1.5">
        <a href="/admin/academic/years"
           class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold
                  transition hover:opacity-80"
           style="border-color: color-mix(in oklab, var(--brand) 30%, transparent);
                  background: color-mix(in oklab, var(--brand) 10%, transparent);
                  color: var(--brand)">
          <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5"/>
          </svg>
          {$yearQ.data.name}
        </a>
        <a href="/admin/academic/years"
           class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold
                  transition hover:opacity-80
                  border-amber-300 bg-amber-50 text-amber-700
                  dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-400">
          No active term
        </a>
      </div>

    {:else}
      <!-- Year + term both active -->
      <div class="flex shrink-0 items-center gap-1.5">
        <!-- Year pill -->
        <a href="/admin/academic/years"
           class="hidden sm:flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5
                  text-xs font-semibold transition hover:opacity-80"
           style="border-color: color-mix(in oklab, var(--brand) 30%, transparent);
                  background: color-mix(in oklab, var(--brand) 10%, transparent);
                  color: var(--brand)">
          <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5"/>
          </svg>
          {$yearQ.data.name}
        </a>
        <!-- Term pill -->
        <a href="/admin/academic/years"
           class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5
                  text-xs font-semibold transition hover:opacity-80
                  {termUrgent
                    ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-400'
                    : 'border-[var(--border)] bg-[var(--hover)] text-[var(--fg)]'}">
          {currentTerm.name}
          {#if daysLeft !== null && daysLeft >= 0}
            <span class="font-normal {termUrgent ? 'text-amber-600 dark:text-amber-500' : 'text-[var(--fg-muted)]'}">
              · {daysLeft}d
            </span>
          {:else if daysLeft !== null && daysLeft < 0}
            <span class="font-normal text-red-500">· ended</span>
          {/if}
        </a>
      </div>
    {/if}
  {/if}

  <!-- Desktop: date -->
  <span class="hidden text-sm text-[var(--fg-muted)] lg:block">{today}</span>

  <!-- Right: theme toggle -->
  <div class="ml-auto flex items-center">
    <ThemeToggle />
  </div>
</header>

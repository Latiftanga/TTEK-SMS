<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import ThemeToggle from './ThemeToggle.svelte';
  import UserMenu from './UserMenu.svelte';
  import { school } from '$lib/stores/school';
  import { currentUser } from '$lib/stores/auth';
  import { userRole } from '$lib/stores/permissions';
  import { getCurrentYear } from '$lib/api/academic';
  import { findCurrentTerm } from '$lib/academicPeriod';
  import { isOnline, isSyncing } from '$lib/offline/sync';

  const today = new Date().toLocaleDateString('en-GH', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });

  const schoolInitials = $derived.by(() => {
    const n = $school?.name ?? 'S';
    const words = n.split(' ').filter((w: string) => w.length > 1);
    return (words.length >= 2 ? words[0][0] + words[1][0] : n.slice(0, 2)).toUpperCase();
  });

  // Only admins and superadmins can navigate to academic year setup.
  const isAdmin = $derived($userRole === 'admin' || ($currentUser?.is_superadmin ?? false));
  const pillTag  = $derived(isAdmin ? 'a' : 'div');
  const setupHref = '/admin/academic/years';

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const currentTerm = $derived(findCurrentTerm($yearQ.data?.terms ?? []));

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
      <!-- No year set — admin-only CTA; non-admins can't fix this -->
      {#if isAdmin}
        <a href={setupHref}
           class="flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold
                  transition hover:opacity-80
                  border-amber-300 bg-amber-50 text-amber-700
                  dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-400">
          <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z"/>
          </svg>
          <span class="hidden sm:inline">Set up academic year</span>
        </a>
      {/if}

    {:else if !currentTerm}
      <!-- Year OK, no active term -->
      <div class="flex shrink-0 items-center gap-1.5">
        <!-- Year pill: clickable for admins, plain for others -->
        <svelte:element this={pillTag} href={isAdmin ? setupHref : undefined}
           class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold
                  {isAdmin ? 'transition hover:opacity-80' : ''}"
           style="border-color: color-mix(in oklab, var(--brand) 30%, transparent);
                  background: color-mix(in oklab, var(--brand) 10%, transparent);
                  color: var(--brand)">
          <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5"/>
          </svg>
          {$yearQ.data.name}
        </svelte:element>
        <!-- "No active term" amber pill: clickable for admins, plain for others -->
        <svelte:element this={pillTag} href={isAdmin ? setupHref : undefined}
           class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold
                  border-amber-300 bg-amber-50 text-amber-700
                  dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-400
                  {isAdmin ? 'transition hover:opacity-80' : ''}">
          No active term
        </svelte:element>
      </div>

    {:else}
      <!-- Year + term both active -->
      <div class="flex shrink-0 items-center gap-1.5">
        <!-- Year pill -->
        <svelte:element this={pillTag} href={isAdmin ? setupHref : undefined}
           class="hidden sm:flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5
                  text-xs font-semibold {isAdmin ? 'transition hover:opacity-80' : ''}"
           style="border-color: color-mix(in oklab, var(--brand) 30%, transparent);
                  background: color-mix(in oklab, var(--brand) 10%, transparent);
                  color: var(--brand)">
          <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5"/>
          </svg>
          {$yearQ.data.name}
        </svelte:element>
        <!-- Term pill -->
        <svelte:element this={pillTag} href={isAdmin ? setupHref : undefined}
           class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5
                  text-xs font-semibold {isAdmin ? 'transition hover:opacity-80' : ''}
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
        </svelte:element>
      </div>
    {/if}
  {/if}

  <!-- Desktop: date -->
  <span class="hidden text-sm text-[var(--fg-muted)] lg:block">{today}</span>

  <!-- Connectivity status -->
  {#if !$isOnline}
    <div class="flex shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border)]
                bg-[var(--hover)] px-2 py-1 text-xs font-medium text-[var(--fg-muted)]">
      <span class="h-2 w-2 shrink-0 rounded-full bg-slate-400 dark:bg-slate-500"></span>
      Offline
    </div>
  {:else if $isSyncing}
    <div class="flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-300
                bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700
                dark:border-amber-700/60 dark:bg-amber-950/30 dark:text-amber-400">
      <svg class="h-3 w-3 shrink-0 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"/>
      </svg>
      Syncing…
    </div>
  {/if}

  <!-- Right: theme + user menu -->
  <div class="ml-auto flex items-center gap-2">
    <ThemeToggle />
    <UserMenu />
  </div>
</header>

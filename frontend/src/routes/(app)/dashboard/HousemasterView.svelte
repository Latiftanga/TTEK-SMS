<script lang="ts">
  import { goto } from '$app/navigation';
  import type { HousemasterDashboard } from '$lib/api/dashboard';

  interface Props { data: HousemasterDashboard; }
  const { data }: Props = $props();
</script>

<div class="mb-6">
  <h1 class="text-xl font-bold text-[var(--fg)]">Good day, {data.greeting_name}</h1>
  {#if data.house_name}
    <p class="text-sm text-[var(--fg-muted)]">{data.house_name}</p>
  {/if}
</div>

<div class="mb-6 grid gap-3 sm:grid-cols-3">
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <p class="text-xs font-medium text-[var(--fg-muted)]">Residents</p>
    <p class="mt-1 text-3xl font-bold text-[var(--fg)]">{data.total_residents}</p>
    <p class="text-xs text-[var(--fg-subtle)]">currently in house</p>
  </div>
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4
              {data.pending_exeats > 0 ? 'border-amber-200 dark:border-amber-800' : ''}">
    <p class="text-xs font-medium text-[var(--fg-muted)]">Pending exeats</p>
    <p class="mt-1 text-3xl font-bold {data.pending_exeats > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--fg)]'}">
      {data.pending_exeats}
    </p>
    <p class="text-xs text-[var(--fg-subtle)]">awaiting approval</p>
  </div>
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4
              {data.off_campus_count > 0 ? 'border-blue-200 dark:border-blue-800' : ''}">
    <p class="text-xs font-medium text-[var(--fg-muted)]">Off campus</p>
    <p class="mt-1 text-3xl font-bold {data.off_campus_count > 0 ? 'text-blue-600 dark:text-blue-400' : 'text-[var(--fg)]'}">
      {data.off_campus_count}
    </p>
    <p class="text-xs text-[var(--fg-subtle)]">students currently out</p>
  </div>
</div>

{#if data.house_id}
  <!-- Quick actions -->
  <div class="mb-4 grid gap-3 sm:grid-cols-2">
    <a href="/housing/{data.house_id}?tab=rollcall"
       class="flex items-center gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]
              px-5 py-4 transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-white"
           style="background-color: var(--brand)">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <p class="font-semibold text-[var(--fg)]">Tonight's Roll Call</p>
        <p class="text-xs text-[var(--fg-muted)]">Mark who is in house</p>
      </div>
      <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
      </svg>
    </a>

    <a href="/housing/{data.house_id}?tab=exeats"
       class="flex items-center gap-4 rounded-2xl border bg-[var(--card)]
              px-5 py-4 transition hover:shadow-sm
              {data.pending_exeats > 0
                ? 'border-amber-200 dark:border-amber-800 hover:border-amber-300 dark:hover:border-amber-700'
                : 'border-[var(--border)] hover:border-[var(--brand)]/40'}">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
                  {data.pending_exeats > 0 ? 'bg-amber-100 dark:bg-amber-900/50' : 'bg-[var(--hover)]'}">
        <svg class="h-5 w-5 {data.pending_exeats > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--fg-muted)]'}"
             fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"/>
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <p class="font-semibold text-[var(--fg)]">Review Exeats</p>
        <p class="text-xs {data.pending_exeats > 0 ? 'font-medium text-amber-600 dark:text-amber-400' : 'text-[var(--fg-muted)]'}">
          {data.pending_exeats > 0 ? `${data.pending_exeats} awaiting approval` : 'No pending requests'}
        </p>
      </div>
      <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
      </svg>
    </a>
  </div>

  <!-- House overview link -->
  <a href="/housing/{data.house_id}"
    class="flex w-full items-center justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)]
           px-5 py-4 transition hover:border-[var(--brand)]/40 hover:shadow-sm">
    <div>
      <p class="font-semibold text-[var(--fg)]">Full house overview</p>
      <p class="text-xs text-[var(--fg-muted)]">Rooms · Students · All activity</p>
    </div>
    <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
    </svg>
  </a>
{/if}

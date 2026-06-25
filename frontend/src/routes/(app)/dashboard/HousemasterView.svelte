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
  <button onclick={() => goto(`/housing/${data.house_id}`)}
    class="flex w-full items-center justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)]
           px-5 py-4 text-left transition hover:border-[var(--brand)]/40 hover:shadow-sm">
    <div>
      <p class="font-semibold text-[var(--fg)]">Manage {data.house_name ?? 'my house'}</p>
      <p class="text-xs text-[var(--fg-muted)]">Exeats · Rooms · Students · Roll calls</p>
    </div>
    <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
    </svg>
  </button>
{/if}

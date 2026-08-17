<script lang="ts">
  import { page } from '$app/stores';
  import { userRole } from '$lib/stores/permissions';

  interface Props { children: import('svelte').Snippet; }
  let { children }: Props = $props();

  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  function isActive(path: string) {
    if (path === '/attendance') return $page.url.pathname === '/attendance';
    return $page.url.pathname.startsWith(path);
  }
</script>

<div class="mx-auto max-w-5xl px-4 py-6">
  <h1 class="mb-4 text-2xl font-bold text-[var(--fg)]">Attendance</h1>

  <!-- overflow-y-hidden is deliberate — see TabBar.svelte's comment: plain
       overflow-x-auto lets the browser compute overflow-y as auto too,
       which can show an unwanted vertical scrollbar on hover. -->
  <div class="mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-[var(--border)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
    <a href="/attendance" title="Mark" class="tab {isActive('/attendance') ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"/>
      </svg>
      <span>Mark</span>
    </a>
    <a href="/attendance/calendar" title="Calendar" class="tab {isActive('/attendance/calendar') ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
      </svg>
      <span>Calendar</span>
    </a>
    {#if canManage}
      <a href="/attendance/schedule" title="Schedule" class="tab {isActive('/attendance/schedule') ? 'tab-active' : ''}">
        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span>Schedule</span>
      </a>
    {/if}
  </div>

  {@render children()}
</div>

<style>
  @reference "tailwindcss";
  .tab       { @apply -mb-px flex min-h-[44px] shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-4 text-sm font-medium text-[var(--fg-muted)] transition hover:text-[var(--fg)]; }
  .tab-active { @apply text-[var(--fg)] border-[var(--brand)]; }
</style>

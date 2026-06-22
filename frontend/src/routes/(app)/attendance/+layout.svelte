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

  <div class="mb-6 flex gap-1 border-b border-[var(--border)]">
    <a href="/attendance"          class="tab {isActive('/attendance')          ? 'tab-active' : ''}">Mark</a>
    <a href="/attendance/calendar" class="tab {isActive('/attendance/calendar') ? 'tab-active' : ''}">Calendar</a>
    {#if canManage}
      <a href="/attendance/schedule" class="tab {isActive('/attendance/schedule') ? 'tab-active' : ''}">Schedule</a>
    {/if}
  </div>

  {@render children()}
</div>

<style>
  @reference "tailwindcss";
  .tab       { @apply px-4 py-2 text-sm font-medium text-[var(--fg-muted)] hover:text-[var(--fg)] border-b-2 border-transparent -mb-px transition; }
  .tab-active { @apply text-[var(--fg)] border-[var(--brand)]; }
</style>

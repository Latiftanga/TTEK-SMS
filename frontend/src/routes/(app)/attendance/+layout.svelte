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
  <div class="mb-6 flex gap-0.5 overflow-x-auto overflow-y-hidden border-b border-[var(--border)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
    <!-- Tab order follows the module's actual workflow lifecycle:
         set up the school-day schedule → generate the calendar from it →
         mark attendance day-to-day → handle excuse follow-ups → review
         accumulated trends.

         Labels hide below sm (icon + title tooltip only) — same treatment
         as the shared TabBar.svelte component uses for the same "too many
         tabs to fit on a phone" problem elsewhere in the app. Five full
         icon+label tabs don't fit a narrow phone width without this, and
         [scrollbar-width:none] means there's no visible affordance that
         more tabs exist off-screen. -->
    {#if canManage}
      <a href="/attendance/schedule" title="Schedule" class="tab {isActive('/attendance/schedule') ? 'tab-active' : ''}">
        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span class="hidden sm:inline">Schedule</span>
      </a>
    {/if}
    <a href="/attendance/calendar" title="Calendar" class="tab {isActive('/attendance/calendar') ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
      </svg>
      <span class="hidden sm:inline">Calendar</span>
    </a>
    <a href="/attendance" title="Mark" class="tab {isActive('/attendance') ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"/>
      </svg>
      <span class="hidden sm:inline">Mark</span>
    </a>
    <a href="/attendance/excuse-requests" title="Excuse Requests" class="tab {isActive('/attendance/excuse-requests') ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z"/>
      </svg>
      <span class="hidden sm:inline">Excuse Requests</span>
    </a>
    <a href="/attendance/trends" title="Trends" class="tab {isActive('/attendance/trends') ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/>
      </svg>
      <span class="hidden sm:inline">Trends</span>
    </a>
  </div>

  {@render children()}
</div>

<style>
  @reference "tailwindcss";
  .tab       { @apply -mb-px flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-3 text-sm font-medium text-[var(--fg-muted)] transition hover:text-[var(--fg)] sm:justify-start sm:px-4; }
  .tab-active { @apply text-[var(--fg)] border-[var(--brand)]; }
</style>

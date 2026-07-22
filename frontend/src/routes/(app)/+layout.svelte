<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import Sidebar   from '$lib/components/Sidebar.svelte';
  import TopBar    from '$lib/components/TopBar.svelte';
  import BottomNav from '$lib/components/BottomNav.svelte';
  import Toast     from '$lib/components/Toast.svelte';
  import { documentTitle } from '$lib/stores/title';
  import { initOfflineSync, pendingOutboxCount, isOnline } from '$lib/offline/sync';
  import { currentUser } from '$lib/stores/auth';
  import { isPortalUser } from '$lib/api/auth';

  const { children } = $props();

  let sidebarOpen = $state(false);

  $effect(() => { initOfflineSync(); });

  // Student (ADMISSION_ID) and guardian (PHONE + guardian_id) logins have no
  // staff permissions and belong on /portal, not this staff app shell —
  // without this a portal user landing here (e.g. a stale bookmark) sees a
  // silently blank dashboard rather than being routed to the page that works
  // for them.
  $effect(() => {
    if ($currentUser && isPortalUser($currentUser)) goto('/portal');
  });
</script>

<svelte:head><title>{$documentTitle}</title></svelte:head>

<div class="flex h-screen overflow-hidden bg-[var(--bg)]">
  <Sidebar open={sidebarOpen} onclose={() => sidebarOpen = false} />

  <div class="flex flex-1 flex-col overflow-hidden">
    <TopBar toggleSidebar={() => sidebarOpen = !sidebarOpen} />

    {#if $pendingOutboxCount > 0}
      <div class="shrink-0 border-b border-amber-200 bg-amber-50 px-4 py-2
                  dark:border-amber-800 dark:bg-amber-950/40">
        <div class="mx-auto flex max-w-7xl items-center justify-between gap-3 lg:px-8">
          <div class="flex items-center gap-2 text-xs font-medium text-amber-700 dark:text-amber-400">
            <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500"></span>
            {#if $isOnline}
              {$pendingOutboxCount} score{$pendingOutboxCount === 1 ? '' : 's'} pending sync
            {:else}
              {$pendingOutboxCount} score{$pendingOutboxCount === 1 ? '' : 's'} will sync when reconnected
            {/if}
          </div>
          {#if $isOnline}
            <a href="/sync"
               class="text-xs font-semibold text-amber-700 underline hover:no-underline dark:text-amber-400">
              Review →
            </a>
          {/if}
        </div>
      </div>
    {/if}

    <main class="flex-1 overflow-y-auto">
      <div class="mx-auto max-w-7xl px-4 py-7 pb-24 lg:px-8 lg:pb-8">
        {#key $page.url.pathname}
          <div class="page-enter">
            {@render children()}
          </div>
        {/key}
      </div>
    </main>
  </div>
</div>

<BottomNav onmore={() => sidebarOpen = !sidebarOpen} />
<Toast />

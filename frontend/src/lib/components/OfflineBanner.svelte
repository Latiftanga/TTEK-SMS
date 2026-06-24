<script lang="ts">
  import { onMount } from 'svelte';
  import { getPendingCount } from '$lib/offline/outbox';
  import { drainWriteOutbox } from '$lib/sync/drainer';
  import { listConflicts } from '$lib/api/sync';

  let online        = $state(true);
  let draining      = $state(false);
  let pendingCount  = $state(0);
  let conflictCount = $state(0);

  async function updatePending() {
    pendingCount = await getPendingCount();
  }

  async function checkConflicts() {
    try {
      const items = await listConflicts();
      conflictCount = items.length;
    } catch { conflictCount = 0; }
  }

  async function handleOnline() {
    online = true;
    if (pendingCount > 0) {
      draining = true;
      await drainWriteOutbox();
      draining = false;
      await updatePending();
    }
    await checkConflicts();
  }

  onMount(() => {
    online = navigator.onLine;
    updatePending();
    checkConflicts();

    const onOnline  = () => handleOnline();
    const onOffline = () => { online = false; updatePending(); };
    window.addEventListener('online',  onOnline);
    window.addEventListener('offline', onOffline);
    const interval  = setInterval(() => { if (online) checkConflicts(); }, 60_000);
    return () => {
      window.removeEventListener('online',  onOnline);
      window.removeEventListener('offline', onOffline);
      clearInterval(interval);
    };
  });

  const shimmer = 'background: linear-gradient(90deg, #B45309, #D97706, #B45309); background-size: 200% 100%; animation: shimmer 2.5s ease-in-out infinite;';
</script>

<!-- Offline -->
{#if !online}
  <div role="status" aria-live="polite"
       class="fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-3 px-4 py-2.5 text-sm font-medium text-white"
       style={shimmer}>
    <span class="relative flex h-2 w-2 shrink-0">
      <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-50"></span>
      <span class="relative inline-flex h-2 w-2 rounded-full bg-white"></span>
    </span>
    <span>
      You're offline
      {#if pendingCount > 0}
        — <strong>{pendingCount} change{pendingCount === 1 ? '' : 's'}</strong> queued to sync
      {:else}
        — changes will sync automatically
      {/if}
    </span>
  </div>

<!-- Draining outbox -->
{:else if draining}
  <div role="status" aria-live="polite"
       class="fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white"
       style="background: var(--brand);">
    <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
    </svg>
    Syncing offline changes…
  </div>

<!-- Online + unresolved conflicts -->
{:else if conflictCount > 0}
  <div role="alert" aria-live="polite"
       class="fixed inset-x-0 top-0 z-[60] flex items-center justify-center gap-2 bg-amber-600 px-4 py-2 text-sm font-medium text-white">
    <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
    </svg>
    <strong>{conflictCount}</strong> sync conflict{conflictCount === 1 ? '' : 's'} need your attention —
    <a href="/sync" class="underline underline-offset-2 hover:no-underline">Resolve now</a>
  </div>
{/if}

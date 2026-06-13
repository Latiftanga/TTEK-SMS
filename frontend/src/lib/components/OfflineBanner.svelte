<script lang="ts">
  import { onMount } from 'svelte';
  import { getPendingCount } from '$lib/offline/outbox';

  let online = $state(true);
  let pendingCount = $state(0);

  async function updatePending() {
    pendingCount = await getPendingCount();
  }

  onMount(() => {
    online = navigator.onLine;
    updatePending();

    const onOnline = () => { online = true; };
    const onOffline = () => { online = false; updatePending(); };

    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);

    // Poll pending count every 30s so it updates after sync
    const interval = setInterval(updatePending, 30_000);

    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      clearInterval(interval);
    };
  });
</script>

{#if !online}
  <div
    role="status"
    aria-live="polite"
    class="fixed top-0 inset-x-0 z-50 flex items-center justify-center gap-2 bg-amber-500 text-white text-sm font-medium py-2 px-4"
  >
    <span class="h-2 w-2 rounded-full bg-white/70 animate-pulse"></span>
    Offline
    {#if pendingCount > 0}
      — {pendingCount} change{pendingCount === 1 ? '' : 's'} waiting to sync
    {:else}
      — changes will sync when connection returns
    {/if}
  </div>
{/if}

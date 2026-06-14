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
    const onOnline  = () => { online = true; };
    const onOffline = () => { online = false; updatePending(); };
    window.addEventListener('online',  onOnline);
    window.addEventListener('offline', onOffline);
    const interval = setInterval(updatePending, 30_000);
    return () => {
      window.removeEventListener('online',  onOnline);
      window.removeEventListener('offline', onOffline);
      clearInterval(interval);
    };
  });
</script>

{#if !online}
  <div role="status" aria-live="polite"
       class="fixed top-0 inset-x-0 z-[60] flex items-center justify-center gap-3
              px-4 py-2.5 text-sm font-medium text-white"
       style="background: linear-gradient(90deg, #B45309, #D97706, #B45309);
              background-size: 200% 100%;
              animation: shimmer 2.5s ease-in-out infinite;">
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
{/if}

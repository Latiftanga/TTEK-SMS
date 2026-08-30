<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import { currentUser } from '$lib/stores/auth';
  import AiTab from '../../(app)/admin/setup/AiTab.svelte';

  onMount(() => {
    const user = get(currentUser);
    if (!user) goto('/');
  });
</script>

<svelte:head><title>TTEK-SMS — Platform AI Default</title></svelte:head>

<div class="min-h-screen bg-[var(--bg)] p-4 sm:p-8">
  <div class="mx-auto max-w-3xl">
    <div class="mb-6">
      <a href="/superadmin" class="text-xs font-medium text-[var(--fg-muted)] hover:text-[var(--fg)]">← Platform Administration</a>
      <h1 class="mt-1 text-lg font-bold text-[var(--fg)]">Platform-Default AI Provider</h1>
      <p class="text-xs text-[var(--fg-muted)]">
        Tagnatek's own shared AI configuration — every school with no AI key of
        its own falls back to this automatically.
      </p>
    </div>

    <AiTab platformDefault={true} />
  </div>
</div>

<script lang="ts">
  import { school } from '$lib/stores/school';
  import { signOut } from '$lib/stores/identity';
  import { documentTitle } from '$lib/stores/title';
  import Toast from '$lib/components/Toast.svelte';

  const { children } = $props();
</script>

<svelte:head><title>{$documentTitle}</title></svelte:head>

<div class="flex min-h-screen flex-col bg-[var(--bg)]">
  <header class="shrink-0 border-b border-[var(--border)] bg-[var(--card)]">
    <div class="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 lg:px-8">
      <div class="flex items-center gap-2.5">
        {#if $school?.logoUrl}
          <img src={$school.logoUrl} alt="" class="h-8 w-8 rounded-lg object-cover" />
        {:else}
          <div class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
               style="background: var(--brand)">
            {($school?.shortName ?? $school?.name ?? 'S')[0]}
          </div>
        {/if}
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-[var(--fg)]">{$school?.name ?? 'Student Portal'}</p>
          <p class="text-[10px] uppercase tracking-wide text-[var(--fg-muted)]">Student &amp; Parent Portal</p>
        </div>
      </div>
      <button onclick={() => signOut()}
        class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        Sign out
      </button>
    </div>
  </header>

  <main class="flex-1">
    <div class="mx-auto max-w-3xl px-4 py-6 lg:px-8">
      {@render children()}
    </div>
  </main>
</div>

<Toast />

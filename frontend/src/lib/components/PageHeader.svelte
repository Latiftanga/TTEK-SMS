<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    description?: string;
    children?: Snippet;
  }

  const { title, description, children }: Props = $props();
</script>

<div class="mb-6 flex items-start justify-between gap-4">
  <div>
    <h1 class="text-xl font-bold tracking-tight text-[var(--fg)]">{title}</h1>
    {#if description}
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">{description}</p>
    {/if}
  </div>
  {#if children}
    <div class="flex shrink-0 items-center gap-2">{@render children()}</div>
  {/if}
</div>

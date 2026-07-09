<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    description?: string;
    children?: Snippet;
  }

  const { title, description, children }: Props = $props();
</script>

<div class="mb-6 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
  <div>
    <h1 class="text-xl font-bold tracking-tight text-[var(--fg)]">{title}</h1>
    {#if description}
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">{description}</p>
    {/if}
  </div>
  {#if children}
    <div class="flex w-full shrink-0 flex-wrap items-center justify-end gap-2 sm:w-auto">
      {@render children()}
    </div>
  {/if}
</div>

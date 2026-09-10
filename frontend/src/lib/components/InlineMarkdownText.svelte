<script lang="ts">
  import { parseInline } from '$lib/markdown';

  interface Props { text: string; }
  const { text }: Props = $props();
  const segments = $derived(parseInline(text));
</script>

{#each segments as seg, i (i)}
  {#if seg.bold}<strong>{seg.text}</strong>
  {:else if seg.code}<code class="rounded bg-[var(--hover)] px-1 py-0.5 text-[0.85em]">{seg.text}</code>
  {:else if seg.italic}<em>{seg.text}</em>
  {:else}{seg.text}{/if}
{/each}

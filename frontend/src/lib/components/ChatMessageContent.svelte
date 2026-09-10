<script lang="ts">
  import { parseSimpleMarkdown } from '$lib/markdown';
  import InlineMarkdownText from './InlineMarkdownText.svelte';

  interface Props { content: string; }
  const { content }: Props = $props();
  const blocks = $derived(parseSimpleMarkdown(content));
</script>

<div class="space-y-2">
  {#each blocks as block, i (i)}
    {#if block.type === 'heading'}
      {#if block.level === 2}
        <h4 class="text-sm font-semibold"><InlineMarkdownText text={block.text} /></h4>
      {:else if block.level === 3}
        <h5 class="text-sm font-semibold"><InlineMarkdownText text={block.text} /></h5>
      {:else}
        <h6 class="text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]"><InlineMarkdownText text={block.text} /></h6>
      {/if}
    {:else if block.type === 'paragraph'}
      <p><InlineMarkdownText text={block.text} /></p>
    {:else if block.type === 'list'}
      {#if block.ordered}
        <ol class="list-decimal space-y-1 pl-5">
          {#each block.items as item, j (j)}<li><InlineMarkdownText text={item} /></li>{/each}
        </ol>
      {:else}
        <ul class="list-disc space-y-1 pl-5">
          {#each block.items as item, j (j)}<li><InlineMarkdownText text={item} /></li>{/each}
        </ul>
      {/if}
    {:else if block.type === 'hr'}
      <hr class="border-[var(--border)]" />
    {/if}
  {/each}
</div>

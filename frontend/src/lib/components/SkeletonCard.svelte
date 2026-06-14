<script lang="ts">
  interface Props { height?: string; lines?: number; }
  const { height = 'h-20', lines = 2 }: Props = $props();
</script>

<div class="rounded-xl bg-[var(--card)] p-4 ring-1 ring-[var(--border)]"
     style="box-shadow: var(--shadow-sm)">
  <div class="{height} flex flex-col justify-between gap-2.5">
    {#each Array(lines) as _, i}
      <div class="skeleton rounded-md
                  {i === 0 ? 'h-2.5 w-2/5' : i === lines - 1 ? 'h-6 w-3/4' : 'h-2.5 w-1/2'}"
           style="animation-delay: {i * 0.1}s"></div>
    {/each}
  </div>
</div>

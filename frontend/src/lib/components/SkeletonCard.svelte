<script lang="ts">
  interface Props { height?: string; lines?: number; }
  const { height = 'h-24', lines = 2 }: Props = $props();
</script>

<div class="rounded-2xl bg-[var(--card)] p-5 ring-1 ring-[var(--border)]"
     style="box-shadow: var(--shadow-sm)">
  <div class="{height} flex flex-col justify-between gap-3">
    {#each Array(lines) as _, i}
      <div class="skeleton rounded-lg
                  {i === 0 ? 'h-3 w-2/5' : i === lines - 1 ? 'h-7 w-3/4' : 'h-3 w-1/2'}"
           style="animation-delay: {i * 0.1}s"></div>
    {/each}
  </div>
</div>

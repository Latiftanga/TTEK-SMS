<script lang="ts">
  interface Props { lines?: number; height?: string; }
  const { lines = 3, height = 'h-24' }: Props = $props();
</script>

<div class="rounded-2xl border border-gray-100 bg-white p-5 {height} animate-pulse">
  {#each Array(lines) as _, i}
    <div
      class="mt-2 rounded bg-gray-100"
      style="height: {i === 0 ? '12px' : '8px'}; width: {i === 0 ? '60%' : '80%'}"
    ></div>
  {/each}
</div>

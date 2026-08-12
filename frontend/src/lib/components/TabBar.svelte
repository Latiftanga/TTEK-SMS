<script lang="ts">
  interface Tab { id: string; label: string; icon?: string; }

  interface Props {
    tabs: Tab[];
    active: string;
    onchange: (id: string) => void;
  }

  const { tabs, active, onchange }: Props = $props();
</script>

<!-- overflow-y-hidden is deliberate, not decorative: setting overflow-x
     without it lets the browser compute overflow-y as `auto` too (a CSS
     spec quirk), which can pop a vertical scrollbar into existence for a
     row that never needed one — sub-pixel/line-height differences between
     icon+label tabs are enough to trigger it. -->
<nav class="-mb-px flex gap-1 overflow-x-auto overflow-y-hidden border-b border-[var(--border)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
     role="tablist" aria-label="tabs">
  {#each tabs as tab}
    <button
      role="tab"
      title={tab.icon ? tab.label : undefined}
      aria-selected={active === tab.id}
      onclick={() => onchange(tab.id)}
      class="relative flex min-h-[44px] shrink-0 items-center gap-1.5 whitespace-nowrap px-3 pb-2.5 pt-0.5 text-sm font-medium transition-colors
             {active === tab.id ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
    >
      {#if tab.icon}
        <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          {@html tab.icon}
        </svg>
      {/if}
      <span class={tab.icon ? 'hidden sm:inline' : ''}>{tab.label}</span>
      {#if active === tab.id}
        <span class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm bg-[var(--brand)]"></span>
      {/if}
    </button>
  {/each}
</nav>

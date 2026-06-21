<script lang="ts">
  interface Tab { id: string; label: string }

  interface Props {
    tabs: Tab[];
    active: string;
    onchange: (id: string) => void;
    variant?: 'underline' | 'pill';
  }

  const { tabs, active, onchange, variant = 'underline' }: Props = $props();
</script>

{#if variant === 'pill'}
  <div class="flex gap-0.5 rounded-lg bg-[var(--hover)] p-0.5" role="tablist">
    {#each tabs as tab}
      <button
        role="tab"
        aria-selected={active === tab.id}
        onclick={() => onchange(tab.id)}
        class="rounded-md px-3 py-1 text-sm font-medium transition-all
               {active === tab.id
                 ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm ring-1 ring-[var(--border)]'
                 : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >{tab.label}</button>
    {/each}
  </div>
{:else}
  <nav class="-mb-px flex gap-1 border-b border-[var(--border)]" role="tablist" aria-label="tabs">
    {#each tabs as tab}
      <button
        role="tab"
        aria-selected={active === tab.id}
        onclick={() => onchange(tab.id)}
        class="relative pb-2.5 pt-0.5 px-3 text-sm font-medium transition-colors
               {active === tab.id ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >
        {tab.label}
        {#if active === tab.id}
          <span class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm bg-[var(--brand)]"></span>
        {/if}
      </button>
    {/each}
  </nav>
{/if}

<script lang="ts">
  interface ActionItem { label: string; icon: string; onClick: () => void; }
  interface Props { actions: ActionItem[]; }
  const { actions }: Props = $props();

  // Same click-outside pattern as UserMenu.svelte — the established version
  // of this interaction in the codebase.
  let open = $state(false);
  let menuEl = $state<HTMLElement | undefined>();

  function handleOutsideClick(e: PointerEvent) {
    if (menuEl && !menuEl.contains(e.target as Node)) open = false;
  }

  $effect(() => {
    if (open) {
      document.addEventListener('pointerdown', handleOutsideClick);
      return () => document.removeEventListener('pointerdown', handleOutsideClick);
    }
  });

  function run(action: ActionItem) {
    open = false;
    action.onClick();
  }
</script>

<!-- Mobile: single "more actions" trigger collapsing every item into a menu -->
<div class="relative sm:hidden" bind:this={menuEl}>
  <button onclick={() => open = !open}
    aria-label="More actions" aria-expanded={open}
    class="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--border)]
           bg-[var(--card)] text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
    <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="5" r="1.75"/><circle cx="12" cy="12" r="1.75"/><circle cx="12" cy="19" r="1.75"/>
    </svg>
  </button>

  {#if open}
    <div role="menu"
      class="absolute right-0 top-full z-50 mt-2 w-48 overflow-hidden rounded-xl
             border border-[var(--border)] bg-[var(--card)] p-1 shadow-xl">
      {#each actions as a}
        <button onclick={() => run(a)}
          class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--fg)]
                 transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            {@html a.icon}
          </svg>
          {a.label}
        </button>
      {/each}
    </div>
  {/if}
</div>

<!-- Desktop / tablet: normal inline buttons, unchanged from before -->
<div class="hidden sm:flex sm:gap-2">
  {#each actions as a}
    <button onclick={a.onClick} class="btn-ghost">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        {@html a.icon}
      </svg>
      {a.label}
    </button>
  {/each}
</div>

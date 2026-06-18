<script lang="ts">
  interface Props {
    title: string;
    description?: string;
    iconPath?: string;
    action?: () => void;
    actionLabel?: string;
  }
  const { title, description, iconPath, action, actionLabel }: Props = $props();
</script>

<!--
  Register-page motif: faint horizontal rules + a thin red margin line on the
  left evoke a blank page from a Ghanaian school exercise book. Rendered at
  near-invisible opacity — texture, not decoration. The content reads cleanly
  at normal viewing; the lines are only perceptible on close inspection.
-->
<div class="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] px-8 py-14 text-center">

  <!-- Register lines (decorative) -->
  <div class="pointer-events-none absolute inset-0" aria-hidden="true">
    {#each [32, 46, 60, 74] as pct}
      <div class="absolute inset-x-0 border-t border-[var(--fg)]"
           style="top: {pct}%; opacity: 0.035;"></div>
    {/each}
    <!-- Red margin line — the signature motif -->
    <div class="absolute inset-y-0 border-l-2 border-red-400"
         style="left: 11%; opacity: 0.18;"></div>
  </div>

  <!-- Content, rendered above the lines -->
  <div class="relative">
    {#if iconPath}
      <div class="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl
                  bg-[var(--brand-dim)]">
        <svg class="h-7 w-7 text-[var(--brand)] opacity-70" fill="none"
             stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          {@html iconPath}
        </svg>
      </div>
    {/if}

    <p class="text-[0.9375rem] font-semibold text-[var(--fg)]">{title}</p>

    {#if description}
      <p class="mt-1.5 text-sm text-[var(--fg-muted)]">{description}</p>
    {/if}

    {#if action && actionLabel}
      <button
        onclick={action}
        class="mt-5 inline-flex items-center rounded-xl px-4 py-2 text-sm font-semibold
               text-white transition hover:opacity-90"
        style="background-color: var(--brand)"
      >
        {actionLabel}
      </button>
    {/if}
  </div>
</div>

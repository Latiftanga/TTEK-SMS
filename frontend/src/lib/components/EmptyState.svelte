<script lang="ts">
  interface Props {
    title: string;
    description?: string;
    iconPath?: string;
    action?: () => void;
    actionLabel?: string;
    secondaryAction?: () => void;
    secondaryActionLabel?: string;
    compact?: boolean;
  }
  const {
    title, description, iconPath, action, actionLabel,
    secondaryAction, secondaryActionLabel, compact = false,
  }: Props = $props();
</script>

<!--
  Register-page motif: faint horizontal rules + a thin red margin line on the
  left evoke a blank page from a Ghanaian school exercise book. Rendered at
  near-invisible opacity — texture, not decoration. The content reads cleanly
  at normal viewing; the lines are only perceptible on close inspection.
-->
{#if compact}
  <div class="flex items-center gap-3 rounded-lg border border-dashed border-[var(--border)] px-4 py-3">
    {#if iconPath}
      <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        {@html iconPath}
      </svg>
    {/if}
    <div class="min-w-0 flex-1">
      <p class="text-sm text-[var(--fg-muted)]">{title}</p>
      {#if description}
        <p class="text-xs text-[var(--fg-muted)]">{description}</p>
      {/if}
    </div>
    {#if action && actionLabel}
      <button onclick={action}
        class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium
               text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        {actionLabel}
      </button>
    {/if}
  </div>
{:else}
  <div class="relative overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] px-8 py-14 text-center">

    <!-- Register lines (decorative) -->
    <div class="pointer-events-none absolute inset-0" aria-hidden="true">
      {#each [32, 46, 60, 74] as pct}
        <div class="absolute inset-x-0 border-t border-[var(--fg)]"
             style="top: {pct}%; opacity: 0.035;"></div>
      {/each}
      <div class="absolute inset-y-0 border-l-2 border-red-400"
           style="left: 11%; opacity: 0.18;"></div>
    </div>

    <div class="relative">
      {#if iconPath}
        <div class="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--brand-dim)]">
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

      {#if (action && actionLabel) || (secondaryAction && secondaryActionLabel)}
        <div class="mt-5 flex items-center justify-center gap-2">
          {#if action && actionLabel}
            <button onclick={action}
              class="inline-flex items-center rounded-xl px-4 py-2 text-sm font-semibold
                     text-white transition hover:opacity-90"
              style="background-color: var(--brand)">
              {actionLabel}
            </button>
          {/if}
          {#if secondaryAction && secondaryActionLabel}
            <button onclick={secondaryAction}
              class="inline-flex items-center rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                     text-[var(--fg)] transition hover:bg-[var(--hover)]">
              {secondaryActionLabel}
            </button>
          {/if}
        </div>
      {/if}
    </div>
  </div>
{/if}

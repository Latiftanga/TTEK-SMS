<script lang="ts">
  // Same icon-row list pattern as MySubjectsCard.svelte/AdminView.svelte's
  // quick-links card — occupancy in the subtitle, pending-exeat badge before
  // the arrow when there's something to review.
  import type { HouseSnapshot } from '$lib/api/dashboard';

  interface Props { houses: HouseSnapshot[]; }
  const { houses }: Props = $props();

  const icon = `<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"/>`;
  const arrow = `<path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>`;
</script>

<div>
  <p class="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">My Houses</p>
  <div class="overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]"
       style="box-shadow: var(--shadow-sm);">
    {#each houses as h (h.id)}
      <a href="/housing/{h.id}" class="group flex items-center gap-3.5 px-4 py-3.5 transition hover:bg-[var(--hover)]">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl
                    bg-[var(--hover)] transition group-hover:bg-[var(--card)]">
          <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html icon}
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[0.8125rem] font-semibold text-[var(--fg)]">{h.name}</p>
          <p class="text-[0.6875rem] text-[var(--fg-muted)]">
            {h.total_residents}{h.capacity ? `/${h.capacity}` : ''} resident{h.total_residents === 1 ? '' : 's'}{h.off_campus_count ? ` · ${h.off_campus_count} off campus` : ''}
          </p>
        </div>
        {#if h.pending_exeats > 0}
          <span class="shrink-0 rounded-full bg-amber-100 dark:bg-amber-900/50 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
            {h.pending_exeats}
          </span>
        {/if}
        <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)] transition-transform group-hover:translate-x-0.5"
             fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          {@html arrow}
        </svg>
      </a>
    {/each}
  </div>
</div>

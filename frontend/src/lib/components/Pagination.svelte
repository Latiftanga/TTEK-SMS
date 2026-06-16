<script lang="ts">
  const { total, pageSize, page, label = 'items', onPageChange } = $props<{
    total: number;
    pageSize: number;
    page: number;
    label?: string;
    onPageChange: (p: number) => void;
  }>();

  const totalPages = $derived(Math.max(1, Math.ceil(total / pageSize)));
  const from       = $derived(total === 0 ? 0 : (page - 1) * pageSize + 1);
  const to         = $derived(Math.min(page * pageSize, total));

  function buildPages(cur: number, tp: number): (number | null)[] {
    if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1);
    const out: (number | null)[] = [1];
    if (cur > 3) out.push(null);
    for (let i = Math.max(2, cur - 1); i <= Math.min(tp - 1, cur + 1); i++) out.push(i);
    if (cur < tp - 2) out.push(null);
    out.push(tp);
    return out;
  }

  const pages = $derived(buildPages(page, totalPages));

  const BTN = "flex h-7 w-7 items-center justify-center rounded-lg text-xs font-medium transition";
</script>

<div class="flex flex-wrap items-center justify-between gap-3">
  <p class="text-xs text-[var(--fg-muted)]">
    {#if total === 0}
      No {label}
    {:else}
      Showing <span class="font-medium text-[var(--fg)]">{from}–{to}</span> of
      <span class="font-medium text-[var(--fg)]">{total}</span> {label}
    {/if}
  </p>

  {#if totalPages > 1}
    <nav class="flex items-center gap-1" aria-label="Pagination">
      <button onclick={() => onPageChange(page - 1)} disabled={page === 1}
        class="{BTN} border border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--card)] hover:text-[var(--fg)] disabled:opacity-40"
        aria-label="Previous page">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
        </svg>
      </button>

      {#each pages as p}
        {#if p === null}
          <span class="{BTN} text-[var(--fg-muted)] cursor-default select-none">…</span>
        {:else}
          <button onclick={() => onPageChange(p)}
            class="{BTN} {p === page
              ? 'text-white shadow-sm'
              : 'text-[var(--fg-muted)] hover:bg-[var(--card)] hover:text-[var(--fg)]'}"
            style={p === page ? 'background-color: var(--brand)' : ''}
            aria-current={p === page ? 'page' : undefined}>
            {p}
          </button>
        {/if}
      {/each}

      <button onclick={() => onPageChange(page + 1)} disabled={page === totalPages}
        class="{BTN} border border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--card)] hover:text-[var(--fg)] disabled:opacity-40"
        aria-label="Next page">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        </svg>
      </button>
    </nav>
  {/if}
</div>

<script lang="ts">
  import { useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listStudents, type StudentSummary } from '$lib/api/students';
  import {
    listStudentFeeRecords, getFeeSummary, listPayments, listDiscounts,
    ghs,
    type FeeRecord, type FeePayment, type FeeSummary, type FeeDiscount,
  } from '$lib/api/fees';
  import PaymentModal  from './PaymentModal.svelte';
  import DiscountModal from './DiscountModal.svelte';
  import FeeLedger     from './FeeLedger.svelte';

  interface Props { termId: string; termName: string; isAdmin: boolean; }
  const { termId, termName, isAdmin }: Props = $props();

  const qc = useQueryClient();

  // ── Student search ─────────────────────────────────────────────────────────────
  let searchText   = $state('');
  let searchFocused = $state(false);
  // Dropdown visible only while the input is focused AND 2+ chars are typed.
  const showResults = $derived(searchFocused && searchText.trim().length >= 2);

  const searchQ       = reactiveQuery(() => ({
    queryKey: ['student-search', searchText.trim()] as const,
    queryFn:  () => listStudents({ search: searchText.trim(), limit: 8, active_only: true }),
    enabled:  searchText.trim().length >= 2,
    staleTime: 10_000,
  }));
  const searchResults = $derived<StudentSummary[]>($searchQ.data ?? []);

  // ── Selected student ───────────────────────────────────────────────────────────
  let selected = $state<StudentSummary | null>(null);

  function pick(s: StudentSummary) { selected = s; searchText = ''; }
  function clear() { selected = null; searchText = ''; }
  function initials(s: StudentSummary) { return (s.first_name[0] + s.last_name[0]).toUpperCase(); }

  // ── Fee data — single combined query keyed by [studentId, termId] ─────────────
  // Four endpoints fetched together as one cache entry. allSettled tolerates partial
  // failures (e.g. 404 on summary when a student has no records yet).
  interface FeeData {
    records:   FeeRecord[];
    payments:  FeePayment[];
    summary:   FeeSummary | null;
    discounts: FeeDiscount[];
  }

  async function fetchFeeData(sid: string, tid: string): Promise<FeeData> {
    const [r, p, s, d] = await Promise.allSettled([
      listStudentFeeRecords(sid, tid),
      listPayments(sid, tid),
      getFeeSummary(sid, tid),
      listDiscounts(sid, tid),
    ]);
    return {
      records:   r.status === 'fulfilled' ? r.value : [],
      payments:  p.status === 'fulfilled' ? p.value : [],
      summary:   s.status === 'fulfilled' ? s.value : null,
      discounts: d.status === 'fulfilled' ? d.value : [],
    };
  }

  // 30s staleTime: reflects payments by colleagues on other terminals promptly
  // while avoiding redundant refetches when toggling between students.
  const feeQ = reactiveQuery(() => ({
    queryKey: ['student-fees', selected?.id ?? '', termId] as const,
    queryFn:  () => fetchFeeData(selected?.id ?? '', termId),
    enabled:  !!selected?.id && !!termId,
    staleTime: 30_000,
  }));
  const records   = $derived<FeeRecord[]>($feeQ.data?.records   ?? []);
  const payments  = $derived<FeePayment[]>($feeQ.data?.payments  ?? []);
  const summary   = $derived<FeeSummary | null>($feeQ.data?.summary ?? null);
  const discounts = $derived<FeeDiscount[]>($feeQ.data?.discounts ?? []);

  // ── Per-record aggregates ──────────────────────────────────────────────────────
  const paidByRecord = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of payments) m.set(p.fee_record_id, (m.get(p.fee_record_id) ?? 0) + Number(p.amount_paid));
    return m;
  });

  const discountsByRecord = $derived.by(() => {
    const m = new Map<string, FeeDiscount[]>();
    for (const d of discounts) m.set(d.fee_record_id, [...(m.get(d.fee_record_id) ?? []), d]);
    return m;
  });

  // Payments sorted newest-first; computed once so the template never re-sorts inline
  const sortedPayments = $derived(
    [...payments].sort((a, b) => b.payment_date.localeCompare(a.payment_date))
  );

  function remaining(r: FeeRecord): number {
    return Math.max(0, Number(r.amount_due) - (paidByRecord.get(r.id) ?? 0));
  }

  // Overall payment progress (0–100) for the top-level progress bar
  const paidPct = $derived.by(() => {
    if (!summary) return 0;
    const due = Number(summary.total_due);
    return due > 0 ? Math.min(100, Math.round((Number(summary.total_paid) / due) * 100)) : 0;
  });

  // ── Modals ─────────────────────────────────────────────────────────────────────
  let payRecord      = $state<FeeRecord | null>(null);
  let discountRecord = $state<FeeRecord | null>(null);

  // Invalidating the combined query key re-fetches all four sub-endpoints atomically.
  function afterMutation() {
    if (selected?.id && termId) {
      qc.invalidateQueries({ queryKey: ['student-fees', selected.id, termId] });
    }
  }
</script>

<!-- ── Student search ─────────────────────────────────────────────────────────── -->
<div class="relative">
  <div class="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
    <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/>
    </svg>
    <input bind:value={searchText}
      onfocus={() => searchFocused = true}
      onblur={() => setTimeout(() => searchFocused = false, 150)}
      placeholder="Search student by name or admission number…"
      class="min-w-0 flex-1 bg-transparent text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:outline-none" />
    {#if selected}
      <button onclick={clear} class="flex min-h-[44px] shrink-0 items-center px-2 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Clear ✕</button>
    {/if}
  </div>
  {#if showResults && searchResults.length > 0}
    <ul class="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl">
      {#each searchResults as s (s.id)}
        <li>
          <button onclick={() => pick(s)} class="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-[var(--hover)]">
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--brand)]/10 text-xs font-bold text-[var(--brand)]">
              {initials(s)}
            </div>
            <div>
              <p class="text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
              <p class="text-xs text-[var(--fg-muted)]">{s.admission_number}{s.current_class_name ? ' · ' + s.current_class_name : ''}</p>
            </div>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if selected}
  <!-- ── Student summary card ────────────────────────────────────────────────────── -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="flex items-center gap-3">
      <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white" style="background: var(--brand)">
        {initials(selected)}
      </div>
      <div class="min-w-0 flex-1">
        <p class="font-semibold text-[var(--fg)]">{selected.display_name}</p>
        <p class="text-xs text-[var(--fg-muted)]">{selected.admission_number}{selected.current_class_name ? ' · ' + selected.current_class_name : ''}</p>
      </div>
      <a href="/students/{selected.id}" class="shrink-0 text-xs font-medium text-[var(--brand)] hover:underline">
        View full profile →
      </a>
    </div>

    {#if $feeQ.isPending}
      <div class="mt-4 grid grid-cols-3 gap-3">
        {#each [0, 1, 2] as _}
          <div class="h-16 animate-pulse rounded-xl bg-[var(--hover)]"></div>
        {/each}
      </div>
    {:else if $feeQ.isError}
      <div class="mt-4 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900 dark:bg-red-950/30">
        <p class="text-sm text-red-700 dark:text-red-400">Could not load fee data.</p>
        <button onclick={() => $feeQ.refetch()}
          class="ml-3 flex min-h-[44px] shrink-0 items-center px-2 text-xs font-semibold text-red-700 underline hover:no-underline dark:text-red-400">
          Retry
        </button>
      </div>
    {:else if summary}
      {@const bal = Number(summary.balance)}
      <div class="mt-4 grid grid-cols-3 gap-3 border-t border-[var(--border)] pt-4">
        <div class="rounded-xl bg-[var(--hover)] px-4 py-3 text-center">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Total Due</p>
          <p class="mt-1 text-base font-bold text-[var(--fg)]">{ghs(summary.total_due)}</p>
        </div>
        <div class="rounded-xl bg-[var(--hover)] px-4 py-3 text-center">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Paid</p>
          <p class="mt-1 text-base font-bold text-green-600 dark:text-green-400">{ghs(summary.total_paid)}</p>
        </div>
        <div class="rounded-xl px-4 py-3 text-center {bal > 0 ? 'bg-red-50 dark:bg-red-950/30' : 'bg-[var(--hover)]'}">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Balance</p>
          <p class="mt-1 text-base font-bold {bal > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}">
            {ghs(summary.balance)}
          </p>
        </div>
      </div>
      <div class="mt-3">
        <div class="mb-1 flex items-center justify-between">
          <span class="text-xs text-[var(--fg-muted)]">Payment progress</span>
          <span class="text-xs font-semibold {paidPct >= 100 ? 'text-green-600 dark:text-green-400' : 'text-[var(--fg-muted)]'}">{paidPct}%</span>
        </div>
        <div class="h-2 overflow-hidden rounded-full bg-[var(--hover)]">
          <div class="h-full rounded-full transition-all duration-500 {paidPct >= 100 ? 'bg-green-500 dark:bg-green-400' : ''}"
               style="width: {paidPct}%; {paidPct < 100 ? 'background: var(--brand)' : ''}"></div>
        </div>
      </div>
    {:else if records.length === 0}
      <p class="mt-4 text-sm text-[var(--fg-muted)]">
        No fee records for {termName}. Use <strong>Fee Setup → Bulk Assign</strong> to create them.
      </p>
    {/if}
  </div>

  {#if !$feeQ.isPending && !$feeQ.isError}
    <FeeLedger
      {records} {sortedPayments} {discountsByRecord} {paidByRecord}
      {termName} {isAdmin} {remaining}
      onPay={(r) => payRecord = r}
      onDiscount={(r) => discountRecord = r}
    />
  {/if}

{:else}
  <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] py-16 text-center">
    <svg class="mb-3 h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803 7.5 7.5 0 0015.803 15.803z"/>
    </svg>
    <p class="text-sm text-[var(--fg-muted)]">Search for a student to view and record fee payments.</p>
  </div>
{/if}

<!-- Modals -->
{#if payRecord && selected}
  <PaymentModal
    record={payRecord}
    {termId}
    remainingBalance={remaining(payRecord)}
    onClose={() => payRecord = null}
    onSuccess={() => { payRecord = null; afterMutation(); }}
  />
{/if}
{#if discountRecord && selected}
  <DiscountModal
    record={discountRecord}
    {termId}
    onClose={() => discountRecord = null}
    onSuccess={() => { discountRecord = null; afterMutation(); }}
  />
{/if}

<script lang="ts">
  import { useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { useTermSelector } from '$lib/termSelector.svelte';
  import {
    listStudentFeeRecords, getFeeSummary, listPayments,
    ghs, PAYMENT_METHOD_LABELS,
    type FeeRecord,
  } from '$lib/api/fees';
  import InstalmentModal from './InstalmentModal.svelte';
  import PaymentModal from '../../fees/PaymentModal.svelte';
  import DiscountModal from '../../fees/DiscountModal.svelte';

  interface Props { studentId: string; }
  const { studentId }: Props = $props();

  const qc = useQueryClient();

  const term = useTermSelector();

  const recordsQ = reactiveQuery(() => ({
    queryKey: ['student-fee-records', studentId, term.termId] as const,
    queryFn:  () => listStudentFeeRecords(studentId, term.termId),
    enabled:  !!term.termId,
    staleTime: 60_000,
  }));
  const paymentsQ = reactiveQuery(() => ({
    queryKey: ['student-payments', studentId, term.termId] as const,
    queryFn:  () => listPayments(studentId, term.termId),
    enabled:  !!term.termId,
    staleTime: 60_000,
  }));
  const summaryQ = reactiveQuery(() => ({
    queryKey: ['student-fee-summary', studentId, term.termId] as const,
    queryFn:  () => getFeeSummary(studentId, term.termId),
    enabled:  !!term.termId,
    staleTime: 60_000,
    retry: false,
  }));

  const paidByRecord = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of $paymentsQ.data ?? []) m.set(p.fee_record_id, (m.get(p.fee_record_id) ?? 0) + parseFloat(p.amount_paid));
    return m;
  });

  function invalidateFees() {
    qc.invalidateQueries({ queryKey: ['student-fee-records',  studentId, term.termId] });
    qc.invalidateQueries({ queryKey: ['student-payments',      studentId, term.termId] });
    qc.invalidateQueries({ queryKey: ['student-fee-summary',   studentId, term.termId] });
  }

  // Payment/Discount modals are the shared fees/PaymentModal.svelte and
  // fees/DiscountModal.svelte components (also used by the standalone /fees
  // page) — this tab used to hand-roll its own copies of both, which had
  // quietly drifted to be missing the Notes field entirely (captured in
  // state, never actually rendered as an input) and never picked up mobile
  // fixes made to the shared originals. One component, two places it's used.
  let payRecord  = $state<FeeRecord | null>(null);
  let discRecord = $state<FeeRecord | null>(null);
  let instRecord = $state<FeeRecord | null>(null);

  function remainingFor(r: FeeRecord): number {
    return Math.max(0, parseFloat(r.amount_due) - (paidByRecord.get(r.id) ?? 0));
  }
</script>

<!-- Term selector -->
<div class="mb-4 flex justify-end">
  <select bind:value={term.termId} class="sel">
    {#each term.terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
  </select>
</div>

{#if $recordsQ.isPending || $paymentsQ.isPending || $summaryQ.isPending}
  <div class="space-y-3">
    {#each [0,1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}
  </div>
{:else}
  <!-- Summary -->
  {#if $summaryQ.data}
    {@const bal = parseFloat($summaryQ.data.balance)}
    <div class="mb-4 grid grid-cols-3 gap-3">
      <div class="rounded-xl bg-[var(--hover)] px-4 py-3 text-center">
        <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Total Due</p>
        <p class="mt-1 text-sm font-bold text-[var(--fg)]">{ghs($summaryQ.data.total_due)}</p>
      </div>
      <div class="rounded-xl bg-[var(--hover)] px-4 py-3 text-center">
        <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Paid</p>
        <p class="mt-1 text-sm font-bold text-green-600 dark:text-green-400">{ghs($summaryQ.data.total_paid)}</p>
      </div>
      <div class="rounded-xl px-4 py-3 text-center {bal > 0 ? 'bg-red-50 dark:bg-red-950/30' : 'bg-[var(--hover)]'}">
        <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Balance</p>
        <p class="mt-1 text-sm font-bold {bal > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600'}">{ghs($summaryQ.data.balance)}</p>
      </div>
    </div>
  {/if}

  <!-- Fee records -->
  {#if ($recordsQ.data ?? []).length > 0}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <div class="border-b border-[var(--border)] px-5 py-3 text-sm font-semibold text-[var(--fg)]">Fee Records</div>
      <div class="divide-y divide-[var(--border)]">
        {#each $recordsQ.data ?? [] as r}
          {@const paid = paidByRecord.get(r.id) ?? 0}
          {@const remaining = Math.max(0, parseFloat(r.amount_due) - paid)}
          <div class="flex items-center gap-3 px-5 py-3">
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-[var(--fg)]">{r.fee_type_name}</p>
              {#if r.due_date}<p class="text-xs text-[var(--fg-muted)]">Due {r.due_date}</p>{/if}
            </div>
            <span class="tabular-nums text-sm text-[var(--fg)]">{ghs(r.amount_due)}</span>
            {#if r.is_waived}
              <span class="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">Waived</span>
            {:else if remaining <= 0}
              <span class="text-xs font-semibold text-green-600 dark:text-green-400">✓ Paid</span>
            {:else}
              <div class="flex flex-wrap gap-1.5">
                <button onclick={() => payRecord = r} class="min-h-[44px] rounded-lg border border-[var(--brand)] px-2.5 text-xs font-semibold text-[var(--brand)] transition hover:bg-[var(--brand)] hover:text-white">Pay</button>
                <button onclick={() => discRecord = r} class="min-h-[44px] rounded-lg border border-[var(--border)] px-2.5 text-xs text-[var(--fg-muted)] transition hover:border-[var(--fg-muted)] hover:text-[var(--fg)]">Discount</button>
                <button onclick={() => instRecord = r} class="min-h-[44px] rounded-lg border border-[var(--border)] px-2.5 text-xs text-[var(--fg-muted)] transition hover:border-[var(--fg-muted)] hover:text-[var(--fg)]">Instalments</button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </div>

    <!-- Payment history -->
    {#if ($paymentsQ.data ?? []).length > 0}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        <div class="border-b border-[var(--border)] px-5 py-3 text-sm font-semibold text-[var(--fg)]">Payment History</div>
        <div class="divide-y divide-[var(--border)]">
          {#each [...($paymentsQ.data ?? [])].sort((a, b) => b.payment_date.localeCompare(a.payment_date)) as p}
            {@const rName = ($recordsQ.data ?? []).find(r => r.id === p.fee_record_id)?.fee_type_name ?? ''}
            <div class="flex items-center gap-4 px-5 py-3">
              <div class="flex-1">
                <p class="text-sm text-[var(--fg)]">{rName || 'Fee payment'}</p>
                <p class="text-xs text-[var(--fg-muted)]">{PAYMENT_METHOD_LABELS[p.payment_method]}{p.reference_number ? ' · ' + p.reference_number : ''}</p>
              </div>
              <div class="text-right">
                <p class="text-sm font-semibold text-green-600 dark:text-green-400">{ghs(p.amount_paid)}</p>
                <p class="text-xs text-[var(--fg-muted)]">{p.payment_date}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {:else}
    <p class="text-sm text-[var(--fg-muted)]">No fee records for this term. Go to Fee Structure setup to assign fees.</p>
  {/if}
{/if}

<!-- Payment / Discount / Instalment modals -->
{#if payRecord}
  <PaymentModal
    record={payRecord} termId={term.termId}
    remainingBalance={remainingFor(payRecord)}
    onClose={() => payRecord = null}
    onSuccess={() => { payRecord = null; invalidateFees(); }}
  />
{/if}
{#if discRecord}
  <DiscountModal
    record={discRecord} termId={term.termId}
    onClose={() => discRecord = null}
    onSuccess={() => { discRecord = null; invalidateFees(); }}
  />
{/if}
{#if instRecord}
  <InstalmentModal record={instRecord} onClose={() => instRecord = null} />
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

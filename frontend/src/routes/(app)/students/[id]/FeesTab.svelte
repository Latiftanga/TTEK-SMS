<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { portal } from '$lib/actions/portal';
  import { listAllTerms, type AcademicTerm } from '$lib/api/academic';
  import {
    listStudentFeeRecords, getFeeSummary, listPayments, applyDiscount, recordPayment,
    ghs, PAYMENT_METHOD_LABELS, DISCOUNT_TYPE_LABELS,
    type FeeRecord, type PaymentMethod, type DiscountType,
  } from '$lib/api/fees';
  import { toast } from '$lib/stores/toast';

  interface Props { studentId: string; }
  const { studentId }: Props = $props();

  const qc = useQueryClient();

  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>([...($termsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  let termId = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  // Three reactive queries — swap queryKey when termId changes; TanStack Query handles caching & dedup
  const recordsOpts  = writable({ queryKey: ['student-fee-records',  studentId, termId] as const, queryFn: () => listStudentFeeRecords(studentId, termId), enabled: !!termId, staleTime: 60_000 });
  const paymentsOpts = writable({ queryKey: ['student-payments',      studentId, termId] as const, queryFn: () => listPayments(studentId, termId),          enabled: !!termId, staleTime: 60_000 });
  const summaryOpts  = writable({ queryKey: ['student-fee-summary',   studentId, termId] as const, queryFn: () => getFeeSummary(studentId, termId),         enabled: !!termId, staleTime: 60_000, retry: false });
  $effect(() => {
    const sid = studentId, tid = termId;
    recordsOpts.set({  queryKey: ['student-fee-records',  sid, tid] as const, queryFn: () => listStudentFeeRecords(sid, tid), enabled: !!tid, staleTime: 60_000 });
    paymentsOpts.set({ queryKey: ['student-payments',      sid, tid] as const, queryFn: () => listPayments(sid, tid),          enabled: !!tid, staleTime: 60_000 });
    summaryOpts.set({  queryKey: ['student-fee-summary',   sid, tid] as const, queryFn: () => getFeeSummary(sid, tid),         enabled: !!tid, staleTime: 60_000, retry: false });
  });
  const recordsQ  = createQuery(recordsOpts);
  const paymentsQ = createQuery(paymentsOpts);
  const summaryQ  = createQuery(summaryOpts);

  const paidByRecord = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of $paymentsQ.data ?? []) m.set(p.fee_record_id, (m.get(p.fee_record_id) ?? 0) + parseFloat(p.amount_paid));
    return m;
  });

  function invalidateFees() {
    qc.invalidateQueries({ queryKey: ['student-fee-records',  studentId, termId] });
    qc.invalidateQueries({ queryKey: ['student-payments',      studentId, termId] });
    qc.invalidateQueries({ queryKey: ['student-fee-summary',   studentId, termId] });
  }

  // ── Payment modal ─────────────────────────────────────────────────────────────
  let payRecord = $state<FeeRecord | null>(null);
  const today = new Date().toISOString().slice(0, 10);
  let payAmount = $state('');
  let payMethod = $state<PaymentMethod>('CASH');
  let payRef    = $state('');
  let payDate   = $state(today);
  let payNotes  = $state('');
  let payError  = $state('');
  const methods = Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][];

  const payMut = createMutation({
    mutationFn: () => recordPayment({
      student_id: studentId,
      fee_record_id: payRecord!.id,
      amount_paid: parseFloat(payAmount),
      payment_method: payMethod,
      reference_number: payRef.trim() || undefined,
      payment_date: payDate,
      notes: payNotes.trim() || undefined,
    }),
    onSuccess: () => { toast.success('Payment recorded.'); payRecord = null; invalidateFees(); },
    onError: (e: unknown) => { payError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.'; },
  });

  function openPay(r: FeeRecord) {
    payRecord = r;
    const remaining = Math.max(0, parseFloat(r.amount_due) - (paidByRecord.get(r.id) ?? 0));
    payAmount = remaining.toFixed(2);
    payMethod = 'CASH'; payRef = ''; payDate = today; payNotes = ''; payError = '';
  }
  function submitPay() {
    payError = '';
    const n = parseFloat(payAmount);
    if (!payAmount || isNaN(n) || n <= 0) { payError = 'Enter a valid amount.'; return; }
    $payMut.mutate();
  }

  // ── Discount modal ────────────────────────────────────────────────────────────
  let discRecord  = $state<FeeRecord | null>(null);
  let discType    = $state<DiscountType>('SCHOLARSHIP');
  let discMode    = $state<'amount' | 'percentage'>('percentage');
  let discValue   = $state('');
  let discReason  = $state('');
  let discError   = $state('');
  const discTypes = Object.entries(DISCOUNT_TYPE_LABELS) as [DiscountType, string][];

  const discMut = createMutation({
    mutationFn: () => applyDiscount({
      student_id: studentId,
      fee_record_id: discRecord!.id,
      discount_type: discType,
      amount:     discMode === 'amount'      ? parseFloat(discValue) : undefined,
      percentage: discMode === 'percentage'  ? parseFloat(discValue) : undefined,
      reason: discReason.trim() || undefined,
    }),
    onSuccess: () => { toast.success('Discount applied.'); discRecord = null; invalidateFees(); },
    onError: (e: unknown) => { discError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.'; },
  });

  function openDisc(r: FeeRecord) { discRecord = r; discType = 'SCHOLARSHIP'; discMode = 'percentage'; discValue = ''; discReason = ''; discError = ''; }
  function submitDisc() {
    discError = '';
    const n = parseFloat(discValue);
    if (!discValue || isNaN(n) || n <= 0) { discError = 'Enter a valid value.'; return; }
    if (discMode === 'percentage' && n > 100) { discError = 'Percentage cannot exceed 100.'; return; }
    $discMut.mutate();
  }
</script>

<!-- Term selector -->
<div class="mb-4 flex justify-end">
  <select bind:value={termId} class="sel">
    {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
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
              <div class="flex gap-1">
                <button onclick={() => openPay(r)} class="rounded-lg border border-[var(--brand)] px-2.5 py-1 text-xs font-semibold text-[var(--brand)] transition hover:bg-[var(--brand)] hover:text-white">Pay</button>
                <button onclick={() => openDisc(r)} class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--fg-muted)] transition hover:border-[var(--fg-muted)] hover:text-[var(--fg)]">Discount</button>
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

<!-- Payment modal -->
{#if payRecord}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <div>
          <h2 class="text-base font-semibold text-[var(--fg)]">Record Payment</h2>
          <p class="text-xs text-[var(--fg-muted)]">{payRecord.fee_type_name} · due {ghs(payRecord.amount_due)}</p>
        </div>
        <button onclick={() => payRecord = null} class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="space-y-3 p-6">
        <div class="grid grid-cols-2 gap-3">
          <label class="block"><span class="lx">Amount (GHS)</span><input type="number" bind:value={payAmount} min="0.01" step="0.01" class="inp mt-1" /></label>
          <label class="block"><span class="lx">Date</span><input type="date" bind:value={payDate} max={today} class="inp mt-1" /></label>
        </div>
        <label class="block"><span class="lx">Method</span>
          <select bind:value={payMethod} class="sel mt-1">{#each methods as [k,v]}<option value={k}>{v}</option>{/each}</select>
        </label>
        <label class="block"><span class="lx">Reference <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span><input bind:value={payRef} class="inp mt-1" /></label>
        {#if payError}<p class="text-xs text-red-500">{payError}</p>{/if}
        <div class="flex justify-end gap-3 pt-1">
          <button onclick={() => payRecord = null} class="btn-ghost">Cancel</button>
          <button onclick={submitPay} disabled={$payMut.isPending} class="btn-primary">{$payMut.isPending ? 'Saving…' : 'Record'}</button>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- Discount modal -->
{#if discRecord}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
        <div>
          <h2 class="text-base font-semibold text-[var(--fg)]">Apply Discount</h2>
          <p class="text-xs text-[var(--fg-muted)]">{discRecord.fee_type_name}</p>
        </div>
        <button onclick={() => discRecord = null} class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="space-y-3 p-6">
        <label class="block"><span class="lx">Discount type</span>
          <select bind:value={discType} class="sel mt-1">{#each discTypes as [k,v]}<option value={k}>{v}</option>{/each}</select>
        </label>
        <div class="flex gap-3">
          <label class="flex cursor-pointer items-center gap-1.5 text-sm">
            <input type="radio" name="disc-mode" value="percentage" bind:group={discMode} /> Percentage
          </label>
          <label class="flex cursor-pointer items-center gap-1.5 text-sm">
            <input type="radio" name="disc-mode" value="amount" bind:group={discMode} /> Fixed amount
          </label>
        </div>
        <label class="block">
          <span class="lx">{discMode === 'percentage' ? 'Percentage (%)' : 'Amount (GHS)'}</span>
          <input type="number" bind:value={discValue} min="0.01" step="0.01" class="inp mt-1" placeholder={discMode === 'percentage' ? '0–100' : '0.00'} />
        </label>
        <label class="block"><span class="lx">Reason <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span><input bind:value={discReason} class="inp mt-1" /></label>
        {#if discError}<p class="text-xs text-red-500">{discError}</p>{/if}
        <div class="flex justify-end gap-3 pt-1">
          <button onclick={() => discRecord = null} class="btn-ghost">Cancel</button>
          <button onclick={submitDisc} disabled={$discMut.isPending} class="btn-primary">{$discMut.isPending ? 'Saving…' : 'Apply'}</button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
</style>

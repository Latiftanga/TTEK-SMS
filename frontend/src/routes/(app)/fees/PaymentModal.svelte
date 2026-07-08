<script lang="ts">
  import { createMutation } from '@tanstack/svelte-query';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';
  import {
    recordPayment, ghs, PAYMENT_METHOD_LABELS,
    type FeeRecord, type PaymentMethod,
  } from '$lib/api/fees';

  interface Props {
    record: FeeRecord;
    studentId: string;
    termId: string;
    remainingBalance: number;
    onClose: () => void;
    onSuccess: () => void;
  }
  const { record, studentId, termId, remainingBalance, onClose, onSuccess }: Props = $props();

  const today = new Date().toISOString().slice(0, 10);
  let amount       = $state(remainingBalance.toFixed(2));
  let method       = $state<PaymentMethod>('CASH');
  let reference    = $state('');
  let paymentDate  = $state(today);
  let notes        = $state('');
  let error        = $state('');

  const methods = Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][];

  const mut = createMutation({
    mutationFn: () => recordPayment({
      student_id: studentId,
      fee_record_id: record.id,
      amount_paid: parseFloat(amount),
      payment_method: method,
      reference_number: reference.trim() || undefined,
      payment_date: paymentDate,
      notes: notes.trim() || undefined,
    }),
    onSuccess: () => {
      toast.success('Payment recorded.');
      onSuccess();
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to record payment.';
    },
  });

  function submit() {
    error = '';
    const n = parseFloat(amount);
    if (!amount || isNaN(n) || n <= 0) { error = 'Enter a valid amount.'; return; }
    if (!paymentDate) { error = 'Select a payment date.'; return; }
    $mut.mutate();
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Record Payment</h2>
        <p class="text-xs text-[var(--fg-muted)]">{record.fee_type_name} · due {ghs(record.amount_due)}</p>
      </div>
      <button onclick={onClose} class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="space-y-4 p-6">
      <div class="grid grid-cols-2 gap-3">
        <label class="block">
          <span class="label-xs">Amount (GHS)</span>
          <input type="number" bind:value={amount} min="0.01" step="0.01"
            class="inp mt-1" placeholder="0.00" />
        </label>
        <label class="block">
          <span class="label-xs">Date</span>
          <input type="date" bind:value={paymentDate} max={today}
            class="inp mt-1" />
        </label>
      </div>

      <label class="block">
        <span class="label-xs">Payment method</span>
        <select bind:value={method} class="sel mt-1">
          {#each methods as [k, v]}<option value={k}>{v}</option>{/each}
        </select>
      </label>

      <label class="block">
        <span class="label-xs">Reference number <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
        <input type="text" bind:value={reference} class="inp mt-1" placeholder="e.g. MTN1234567" />
      </label>

      <label class="block">
        <span class="label-xs">Notes <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
        <input type="text" bind:value={notes} class="inp mt-1" />
      </label>

      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}

      <div class="flex justify-end gap-3 pt-1">
        <button onclick={onClose} class="btn-ghost">Cancel</button>
        <button onclick={submit} disabled={$mut.isPending} class="btn-primary">
          {$mut.isPending ? 'Saving…' : 'Record Payment'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .sel  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

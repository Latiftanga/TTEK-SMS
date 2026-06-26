<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { portal } from '$lib/actions/portal';
  import { listInstalments, setInstalmentPlan, ghs, type FeeRecord, type Instalment } from '$lib/api/fees';
  import { toast } from '$lib/stores/toast';

  interface Props { record: FeeRecord; onClose: () => void; }
  const { record, onClose }: Props = $props();

  const qc = useQueryClient();

  const planQ = createQuery({
    queryKey: ['instalments', record.id],
    queryFn: () => listInstalments(record.id),
    staleTime: 30_000,
  });

  // ── Form state ────────────────────────────────────────────────────────────────
  type Row = { amount: string; due_date: string };
  let rows = $state<Row[]>([{ amount: '', due_date: '' }, { amount: '', due_date: '' }, { amount: '', due_date: '' }]);
  let formError = $state('');
  let showForm  = $state(false);

  $effect(() => {
    const existing = $planQ.data;
    if (existing?.length) {
      rows = existing.map(i => ({ amount: parseFloat(i.amount).toFixed(2), due_date: i.due_date }));
      showForm = true;
    }
  });

  function addRow() { rows = [...rows, { amount: '', due_date: '' }]; }
  function removeRow(i: number) { rows = rows.filter((_, idx) => idx !== i); }

  const saveMut = createMutation({
    mutationFn: () => {
      const items = rows.map((r, idx) => ({
        instalment_number: idx + 1,
        amount: parseFloat(r.amount),
        due_date: r.due_date,
      }));
      return setInstalmentPlan(record.id, items);
    },
    onSuccess: () => {
      toast.success('Instalment plan saved.');
      qc.invalidateQueries({ queryKey: ['instalments', record.id] });
      onClose();
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to save.';
    },
  });

  function submit() {
    formError = '';
    for (const r of rows) {
      const n = parseFloat(r.amount);
      if (!r.amount || isNaN(n) || n <= 0) { formError = 'All instalments need a positive amount.'; return; }
      if (!r.due_date) { formError = 'All instalments need a due date.'; return; }
    }
    if (rows.length === 0) { formError = 'Add at least one instalment.'; return; }
    $saveMut.mutate();
  }

  const totalPlanned = $derived(
    rows.reduce((s, r) => s + (parseFloat(r.amount) || 0), 0)
  );
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">

    <!-- Header -->
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Instalment Plan</h2>
        <p class="text-xs text-[var(--fg-muted)]">{record.fee_type_name} · {ghs(record.amount_due)}</p>
      </div>
      <button onclick={onClose}
        class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <div class="max-h-[70vh] overflow-y-auto p-6">

      {#if $planQ.isPending}
        <div class="space-y-2">
          {#each [0,1,2] as _}
            <div class="h-10 animate-pulse rounded-lg bg-[var(--hover)]"></div>
          {/each}
        </div>

      {:else if !showForm && !$planQ.data?.length}
        <!-- No plan yet -->
        <p class="mb-5 text-sm text-[var(--fg-muted)]">No instalment schedule set for this fee. Set one below.</p>
        <button onclick={() => showForm = true}
          class="w-full rounded-xl border border-dashed border-[var(--brand)] py-2.5 text-sm
                 font-medium text-[var(--brand)] transition hover:bg-[var(--brand)]/5">
          + Create plan
        </button>

      {:else}
        <!-- View existing or edit -->
        {#if $planQ.data?.length && !showForm}
          <!-- Read-only schedule -->
          <div class="mb-4 overflow-hidden rounded-xl border border-[var(--border)]">
            <div class="border-b border-[var(--border)] bg-[var(--hover)] px-4 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--fg-muted)]">
              Current schedule
            </div>
            <div class="divide-y divide-[var(--border)]">
              {#each ($planQ.data ?? []).sort((a: Instalment, b: Instalment) => a.instalment_number - b.instalment_number) as inst}
                <div class="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span class="w-5 text-center text-xs font-semibold text-[var(--fg-muted)]">{inst.instalment_number}</span>
                  <span class="flex-1 text-[var(--fg)]">{inst.due_date}</span>
                  <span class="tabular-nums text-[var(--fg)]">{ghs(inst.amount)}</span>
                  {#if inst.is_paid}
                    <span class="rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-950/30 dark:text-green-300">Paid</span>
                  {:else}
                    <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">Pending</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
          <button onclick={() => showForm = true}
            class="mb-4 text-xs font-medium text-[var(--brand)] transition hover:underline">
            Replace plan
          </button>
        {/if}

        {#if showForm}
          <!-- Editable rows -->
          <div class="mb-3 space-y-2">
            {#each rows as row, i (i)}
              <div class="flex items-center gap-2">
                <span class="w-5 shrink-0 text-center text-xs text-[var(--fg-muted)]">{i + 1}</span>
                <input
                  type="number" min="0.01" step="0.01"
                  bind:value={row.amount}
                  placeholder="Amount"
                  class="inp w-28 shrink-0" />
                <input
                  type="date"
                  bind:value={row.due_date}
                  class="inp flex-1" />
                <button
                  onclick={() => removeRow(i)}
                  disabled={rows.length <= 1}
                  class="shrink-0 rounded-lg p-1 text-[var(--fg-subtle)] transition hover:text-red-500 disabled:opacity-30">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                </button>
              </div>
            {/each}
          </div>

          <button onclick={addRow}
            class="mb-4 text-xs font-medium text-[var(--brand)] transition hover:underline">
            + Add instalment
          </button>

          <!-- Total vs due comparison -->
          <div class="mb-4 flex items-center justify-between rounded-xl bg-[var(--hover)] px-4 py-2 text-xs">
            <span class="text-[var(--fg-muted)]">Plan total</span>
            <span class="font-semibold {Math.abs(totalPlanned - parseFloat(record.amount_due)) > 0.01 ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--fg)]'}">
              {ghs(totalPlanned)}
              {#if Math.abs(totalPlanned - parseFloat(record.amount_due)) > 0.01}
                · fee is {ghs(record.amount_due)}
              {/if}
            </span>
          </div>

          {#if formError}<p class="mb-3 text-xs text-red-500">{formError}</p>{/if}

          <div class="flex justify-end gap-3">
            <button onclick={() => { showForm = false; formError = ''; }} class="btn-ghost">Cancel</button>
            <button onclick={submit} disabled={$saveMut.isPending} class="btn-primary">
              {$saveMut.isPending ? 'Saving…' : 'Save Plan'}
            </button>
          </div>
        {/if}
      {/if}

    </div>
  </div>
</div>

<style>
  @reference "tailwindcss";
  .inp { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .btn-primary { @apply rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50; background: var(--brand); }
  .btn-ghost   { @apply rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]; }
</style>

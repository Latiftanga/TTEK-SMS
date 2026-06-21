<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';
  import { createFeeStructure, updateFeeStructure, ghs, type FeeType, type FeeStructure } from '$lib/api/fees';
  import type { SchoolClass } from '$lib/api/academic';

  interface Props {
    editing: FeeStructure | null;
    termId: string;
    termName: string;
    feeTypes: FeeType[];
    classes: SchoolClass[];
    onClose: () => void;
  }
  const { editing, termId, termName, feeTypes, classes, onClose }: Props = $props();

  const qc = useQueryClient();

  // Unique year groups from the school's classes, sorted ascending
  const yearGroups = $derived([...new Set(classes.map(c => c.year_group))].sort((a, b) => a - b));
  // Map year_group → representative class name prefix for display (e.g. "SHS 1", "JHS 3")
  function yearGroupLabel(yg: number) {
    const cls = classes.find(c => c.year_group === yg);
    return cls ? `${cls.level} ${yg}` : `Year ${yg}`;
  }

  let feeTypeId    = $state(editing?.fee_type_id ?? '');
  let amount       = $state(editing?.amount ?? '');
  let isMandatory  = $state(editing?.is_mandatory ?? true);
  let yearGroup    = $state<string>(editing?.applies_to_year_group?.toString() ?? '');
  let error        = $state('');

  const activeFeeTypes = $derived(feeTypes.filter(t => t.is_active));

  const mut = createMutation({
    mutationFn: () => editing
      ? updateFeeStructure(editing.id, { amount: parseFloat(amount), is_mandatory: isMandatory })
      : createFeeStructure({
          academic_term_id: termId,
          fee_type_id: feeTypeId,
          amount: parseFloat(amount),
          is_mandatory: isMandatory,
          applies_to_year_group: yearGroup ? parseInt(yearGroup) : undefined,
        }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fee-structures', termId] });
      toast.success(editing ? 'Structure updated.' : 'Fee structure created.');
      onClose();
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Something went wrong.';
    },
  });

  function submit() {
    error = '';
    if (!editing && !feeTypeId) { error = 'Select a fee type.'; return; }
    const n = parseFloat(amount);
    if (!amount || isNaN(n) || n <= 0) { error = 'Enter a valid amount.'; return; }
    $mut.mutate();
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">{editing ? 'Edit' : 'Add'} Fee Structure</h2>
        <p class="text-xs text-[var(--fg-muted)]">{termName}</p>
      </div>
      <button onclick={onClose} class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="space-y-3 p-6">
      {#if editing}
        <div class="rounded-xl bg-[var(--hover)] px-3 py-2 text-sm text-[var(--fg)]">{editing.fee_type_name}</div>
      {:else}
        <label class="block">
          <span class="label-xs">Fee type</span>
          <select bind:value={feeTypeId} class="sel mt-1">
            <option value="">Select fee type…</option>
            {#each activeFeeTypes as t}<option value={t.id}>{t.name} ({t.code})</option>{/each}
          </select>
        </label>
      {/if}

      <label class="block">
        <span class="label-xs">Amount (GHS)</span>
        <input type="number" bind:value={amount} min="0.01" step="0.01" class="inp mt-1" placeholder="0.00" />
      </label>

      {#if !editing}
        <label class="block">
          <span class="label-xs">Applies to year group <span class="font-normal text-[var(--fg-subtle)]">(leave blank for all)</span></span>
          <select bind:value={yearGroup} class="sel mt-1">
            <option value="">All year groups</option>
            {#each yearGroups as yg}
              <option value={yg.toString()}>{yearGroupLabel(yg)}</option>
            {/each}
          </select>
        </label>
      {/if}

      <label class="flex cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
        <input type="checkbox" bind:checked={isMandatory} class="rounded" />
        Mandatory
      </label>

      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}

      <div class="flex justify-end gap-3 pt-2">
        <button onclick={onClose} class="btn-ghost">Cancel</button>
        <button onclick={submit} disabled={$mut.isPending} class="btn-primary">
          {$mut.isPending ? 'Saving…' : editing ? 'Save' : 'Add'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

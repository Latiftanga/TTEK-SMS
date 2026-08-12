<script lang="ts">
  import { createMutation } from '@tanstack/svelte-query';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';
  import { applyDiscount, DISCOUNT_TYPE_LABELS, type FeeRecord, type DiscountType } from '$lib/api/fees';

  interface Props {
    record: FeeRecord;
    termId: string;
    onClose: () => void;
    onSuccess: () => void;
  }
  const { record, termId, onClose, onSuccess }: Props = $props();

  type Mode = 'percentage' | 'amount';
  let discountType = $state<DiscountType>('BURSARY');
  let mode         = $state<Mode>('percentage');
  let value        = $state('');
  let reason       = $state('');
  let error        = $state('');

  const types = Object.entries(DISCOUNT_TYPE_LABELS) as [DiscountType, string][];

  const mut = createMutation({
    mutationFn: () => applyDiscount({
      fee_record_id: record.id,
      discount_type: discountType,
      percentage: mode === 'percentage' ? parseFloat(value) : undefined,
      amount:     mode === 'amount'     ? parseFloat(value) : undefined,
      reason:     reason.trim() || undefined,
    }),
    onSuccess: () => {
      toast.success('Discount applied.');
      onSuccess();
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not apply discount.';
    },
  });

  function submit() {
    error = '';
    const n = parseFloat(value);
    if (!value || isNaN(n) || n <= 0) { error = 'Enter a valid value.'; return; }
    if (mode === 'percentage' && n > 100) { error = 'Percentage cannot exceed 100.'; return; }
    $mut.mutate();
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="flex max-h-[90vh] w-full max-w-sm flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Apply Discount</h2>
        <p class="text-xs text-[var(--fg-muted)]">{record.fee_type_name}</p>
      </div>
      <button onclick={onClose} aria-label="Close"
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- max-h + overflow-y-auto so a phone's on-screen keyboard covering
         the lower half of the screen can't hide the Apply button below the
         fold — the header stays fixed, only this section scrolls. -->
    <div class="space-y-4 overflow-y-auto p-6">
      <label class="block">
        <span class="lx">Discount type</span>
        <select bind:value={discountType} class="sel mt-1">
          {#each types as [k, v]}<option value={k}>{v}</option>{/each}
        </select>
      </label>

      <div>
        <span class="lx">Discount value</span>
        <div class="mt-1 flex rounded-xl border border-[var(--border)] bg-[var(--bg)] overflow-hidden">
          <button onclick={() => mode = 'percentage'}
            class="min-h-[44px] px-3 text-xs font-semibold transition
                   {mode === 'percentage' ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
            %
          </button>
          <button onclick={() => mode = 'amount'}
            class="min-h-[44px] border-l border-[var(--border)] px-3 text-xs font-semibold transition
                   {mode === 'amount' ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
            GHS
          </button>
          <input type="number" inputmode="decimal" bind:value min="0.01" step={mode === 'percentage' ? '1' : '0.01'}
            placeholder={mode === 'percentage' ? '0–100' : '0.00'}
            class="min-h-[44px] flex-1 border-l border-[var(--border)] bg-transparent px-3 text-sm text-[var(--fg)] focus:outline-none" />
        </div>
      </div>

      <label class="block">
        <span class="lx">Reason <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
        <input bind:value={reason} class="inp mt-1" placeholder="e.g. Academic merit scholarship" />
      </label>

      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}

      <div class="flex justify-end gap-3 pt-1">
        <button onclick={onClose} class="btn-ghost min-h-[44px]">Cancel</button>
        <button onclick={submit} disabled={$mut.isPending} class="btn-primary min-h-[44px]">
          {$mut.isPending ? 'Applying…' : 'Apply discount'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .sel { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';
  import { createFeeType, updateFeeType, type FeeType } from '$lib/api/fees';

  interface Props {
    editing: FeeType | null;
    onClose: () => void;
  }
  const { editing, onClose }: Props = $props();

  const qc = useQueryClient();

  let name        = $state(editing?.name ?? '');
  let code        = $state(editing?.code ?? '');
  let description = $state(editing?.description ?? '');
  let isRecurring = $state(editing?.is_recurring ?? true);
  let isActive    = $state(editing?.is_active ?? true);
  let error       = $state('');

  const mut = createMutation({
    mutationFn: () => editing
      ? updateFeeType(editing.id, { name, description: description || undefined, is_recurring: isRecurring, is_active: isActive })
      : createFeeType({ name, code, description: description || undefined, is_recurring: isRecurring }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fee-types'] });
      toast.success(editing ? 'Fee type updated.' : 'Fee type created.');
      onClose();
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Something went wrong.';
    },
  });

  function submit() {
    error = '';
    if (!name.trim()) { error = 'Name is required.'; return; }
    if (!editing && !code.trim()) { error = 'Code is required.'; return; }
    $mut.mutate();
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="flex max-h-[90vh] w-full max-w-sm flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <h2 class="text-base font-semibold text-[var(--fg)]">{editing ? 'Edit' : 'New'} Fee Type</h2>
      <button onclick={onClose} aria-label="Close"
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="space-y-3 overflow-y-auto p-6">
      <label class="block">
        <span class="label-xs">Name</span>
        <input bind:value={name} class="inp mt-1" placeholder="e.g. Tuition Fee" />
      </label>
      {#if !editing}
        <label class="block">
          <span class="label-xs">Code</span>
          <input bind:value={code} class="inp mt-1" placeholder="e.g. TUITION" />
        </label>
      {/if}
      <label class="block">
        <span class="label-xs">Description <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
        <input bind:value={description} class="inp mt-1" />
      </label>
      <div class="flex flex-wrap items-center gap-4">
        <label class="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
          <input type="checkbox" bind:checked={isRecurring} class="rounded" />
          Recurring per term
        </label>
        {#if editing}
          <label class="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
            <input type="checkbox" bind:checked={isActive} class="rounded" />
            Active
          </label>
        {/if}
      </div>

      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}

      <div class="flex justify-end gap-3 pt-2">
        <button onclick={onClose} class="btn-ghost min-h-[44px]">Cancel</button>
        <button onclick={submit} disabled={$mut.isPending} class="btn-primary min-h-[44px]">
          {$mut.isPending ? 'Saving…' : editing ? 'Save' : 'Create'}
        </button>
      </div>
    </div>
  </div>
</div>

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

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

  type ScopeMode = 'all' | 'class' | 'cohort';

  // Unique sorted year groups + unique programmes from classes
  const yearGroups  = $derived([...new Set(classes.map(c => c.year_group))].sort((a, b) => a - b));
  const programmes  = $derived([...new Map(
    classes.filter(c => c.programme_id && c.programme_name)
           .map(c => [c.programme_id, { id: c.programme_id!, name: c.programme_name! }])
  ).values()]);
  const activeClasses = $derived(classes.filter(c => c.is_active).sort((a, b) => a.display_name.localeCompare(b.display_name)));

  function yearGroupLabel(yg: number) {
    const cls = classes.find(c => c.year_group === yg);
    return cls ? `${cls.level} ${yg}` : `Year ${yg}`;
  }

  // Form state
  let feeTypeId    = $state(editing?.fee_type_id ?? '');
  let amount       = $state(editing?.amount ?? '');
  let isMandatory  = $state(editing?.is_mandatory ?? true);
  let boardingOnly = $state(editing?.boarding_only ?? false);
  let error        = $state('');

  // Scope state — derive initial mode from editing record
  const initMode = (): ScopeMode => {
    if (!editing) return 'all';
    if (editing.applies_to_class_id) return 'class';
    if (editing.applies_to_year_group || editing.applies_to_programme_id) return 'cohort';
    return 'all';
  };
  let scopeMode    = $state<ScopeMode>(initMode());
  let classId      = $state(editing?.applies_to_class_id ?? '');
  let yearGroup    = $state(editing?.applies_to_year_group?.toString() ?? '');
  let programmeId  = $state(editing?.applies_to_programme_id ?? '');

  const activeFeeTypes = $derived(feeTypes.filter(t => t.is_active));

  const mut = createMutation({
    mutationFn: () => editing
      ? updateFeeStructure(editing.id, { amount: parseFloat(amount), is_mandatory: isMandatory })
      : createFeeStructure({
          academic_term_id: termId,
          fee_type_id: feeTypeId,
          amount: parseFloat(amount),
          is_mandatory: isMandatory,
          applies_to_class_id:     scopeMode === 'class'  ? classId     || undefined : undefined,
          applies_to_year_group:   scopeMode === 'cohort' ? (yearGroup ? parseInt(yearGroup) : undefined) : undefined,
          applies_to_programme_id: scopeMode === 'cohort' ? programmeId || undefined : undefined,
          boarding_only: boardingOnly,
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
    if (scopeMode === 'class' && !classId) { error = 'Select a class.'; return; }
    $mut.mutate();
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="flex max-h-[90vh] w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">{editing ? 'Edit' : 'Add'} Fee Structure</h2>
        <p class="text-xs text-[var(--fg-muted)]">{termName}</p>
      </div>
      <button onclick={onClose} aria-label="Close"
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="space-y-4 overflow-y-auto p-6">
      <!-- Fee type -->
      {#if editing}
        <div class="rounded-xl bg-[var(--hover)] px-3 py-2 text-sm font-medium text-[var(--fg)]">{editing.fee_type_name}</div>
      {:else}
        <label class="block">
          <span class="lx">Fee type</span>
          <select bind:value={feeTypeId} class="sel mt-1">
            <option value="">Select fee type…</option>
            {#each activeFeeTypes as t}<option value={t.id}>{t.name} ({t.code})</option>{/each}
          </select>
        </label>
      {/if}

      <!-- Amount -->
      <label class="block">
        <span class="lx">Amount (GHS)</span>
        <input type="number" inputmode="decimal" bind:value={amount} min="0.01" step="0.01" class="inp mt-1" placeholder="0.00" />
      </label>

      <!-- Scope (only on create) -->
      {#if !editing}
        <fieldset class="space-y-2">
          <legend class="lx">Who pays this fee?</legend>
          <div class="mt-1 space-y-1">
            {#each ([['all','All enrolled students'],['class','Specific class (stream)'],['cohort','Year group / programme']] as const) as [mode, label]}
              <label class="flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 transition hover:bg-[var(--hover)] {scopeMode === mode ? 'bg-[var(--hover)]' : ''}">
                <input type="radio" name="scope" value={mode} bind:group={scopeMode} class="accent-[var(--brand)]" />
                <span class="text-sm text-[var(--fg)]">{label}</span>
              </label>
            {/each}
          </div>

          {#if scopeMode === 'class'}
            <select bind:value={classId} class="sel">
              <option value="">Select class…</option>
              {#each activeClasses as c}<option value={c.id}>{c.display_name}</option>{/each}
            </select>

          {:else if scopeMode === 'cohort'}
            <div class="grid grid-cols-2 gap-3">
              <label class="block">
                <span class="lx">Year group <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
                <select bind:value={yearGroup} class="sel mt-1">
                  <option value="">Any year</option>
                  {#each yearGroups as yg}<option value={yg.toString()}>{yearGroupLabel(yg)}</option>{/each}
                </select>
              </label>
              {#if programmes.length > 0}
                <label class="block">
                  <span class="lx">Programme <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
                  <select bind:value={programmeId} class="sel mt-1">
                    <option value="">Any programme</option>
                    {#each programmes as p}<option value={p.id}>{p.name}</option>{/each}
                  </select>
                </label>
              {/if}
            </div>
          {/if}
        </fieldset>

        <!-- Boarding only (stacks with any scope) -->
        <label class="flex cursor-pointer items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2.5 transition hover:bg-[var(--hover)]">
          <input type="checkbox" bind:checked={boardingOnly} class="accent-[var(--brand)]" />
          <span class="text-sm text-[var(--fg)]">Boarding students only</span>
        </label>
      {/if}

      <!-- Mandatory -->
      <label class="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
        <input type="checkbox" bind:checked={isMandatory} class="accent-[var(--brand)]" />
        Mandatory fee
      </label>

      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}

      <div class="flex justify-end gap-3 pt-1">
        <button onclick={onClose} class="btn-ghost min-h-[44px]">Cancel</button>
        <button onclick={submit} disabled={$mut.isPending} class="btn-primary min-h-[44px]">
          {$mut.isPending ? 'Saving…' : editing ? 'Save' : 'Add'}
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

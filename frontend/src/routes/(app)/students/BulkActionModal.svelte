<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { bulkPromoteStudents, type PromotionRecordCreate } from '$lib/api/students';
  import { listAllTerms, type SchoolClass, type AcademicTerm } from '$lib/api/academic';
  import { sortTermsDesc } from '$lib/academicPeriod';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';
  import { detailOf, isLocked } from '$lib/apiError';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  interface Props {
    selected: Set<string>;
    classes: SchoolClass[];
    onClear: () => void;
  }
  const { selected, classes, onClear }: Props = $props();

  const qc = useQueryClient();

  let action        = $state<'promote' | 'repeat' | 'demote' | null>(null);
  let targetClassId = $state('');
  let targetTermId  = $state('');
  let error         = $state('');

  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>(sortTermsDesc($termsQ.data ?? []));
  const selectedTerm = $derived(terms.find(t => t.id === targetTermId));
  const count        = $derived(selected.size);

  const LABELS = {
    promote: { title: 'Promote', desc: 'Assign to a higher class and enrol for a new term.' },
    repeat:  { title: 'Repeat',  desc: 'Re-enrol in the same or another class for the next term.' },
    demote:  { title: 'Demote',  desc: 'Assign to a lower class and enrol for a new term.' },
  };
  const ACTION_TO_TYPE: Record<NonNullable<typeof action>, PromotionRecordCreate['graduation_type']> = {
    promote: 'PROMOTED', repeat: 'REPEATED', demote: 'DEMOTED',
  };

  let overrideNeeded = $state(false);
  let overrideError  = $state('');

  const bulkMut = createMutation({
    mutationFn: (overrideReason?: string) => {
      if (!selectedTerm) throw new Error('No term selected.');
      const records: PromotionRecordCreate[] = [...selected].map(sid => ({
        student_id: sid, class_id: targetClassId, graduation_type: ACTION_TO_TYPE[action!],
      }));
      return bulkPromoteStudents({
        academic_year_id: selectedTerm.academic_year_id,
        academic_term_id: targetTermId,
        records,
        override_reason: overrideReason,
      });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['students'] });
      overrideNeeded = false; overrideError = '';
      toast.success(`${res.processed} student(s) updated. Skipped: ${res.skipped} (already processed for this year).`);
      closeModal(); onClear();
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { overrideNeeded = true; overrideError = detailOf(e) ?? 'This mismatch needs a reason.'; return; }
      error = detailOf(e) ?? 'Something went wrong.';
    },
  });

  function openAction(a: typeof action) { action = a; targetClassId = ''; targetTermId = ''; error = ''; }
  function closeModal() { action = null; targetClassId = ''; targetTermId = ''; error = ''; overrideNeeded = false; overrideError = ''; }

  function confirm() {
    error = '';
    if (!targetClassId) { error = 'Select a target class.'; return; }
    if (!targetTermId)  { error = 'Select a target term.'; return; }
    $bulkMut.mutate(undefined);
  }
</script>

<!-- Floating action bar -->
{#if count > 0}
  <div use:portal class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
    <div class="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 shadow-xl">
      <span class="text-sm font-medium text-[var(--fg)]">{count} selected</span>
      <div class="mx-2 h-4 w-px bg-[var(--border)]"></div>
      {#each (['promote', 'repeat', 'demote'] as const) as a}
        <button onclick={() => openAction(a)}
          class="min-h-[44px] rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--fg)] transition hover:bg-[var(--hover)]">
          {a === 'promote' ? 'Promote ↑' : a === 'repeat' ? 'Repeat ↺' : 'Demote ↓'}
        </button>
      {/each}
      <button onclick={onClear} aria-label="Clear selection"
        class="ml-1 flex min-h-[44px] min-w-[44px] items-center justify-center text-sm text-[var(--fg-muted)] transition hover:text-[var(--fg)]">✕</button>
    </div>
  </div>
{/if}

<!-- Action modal -->
{#if action}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="flex max-h-[90vh] w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
      <div class="shrink-0 p-6 pb-0">
        <h2 class="text-lg font-bold text-[var(--fg)]">{LABELS[action].title} Students</h2>
        <p class="mb-5 mt-1 text-sm text-[var(--fg-muted)]">
          {count} student{count !== 1 ? 's' : ''} selected. {LABELS[action].desc}
        </p>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-6">
        <div class="space-y-3">
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Target class</span>
            <select bind:value={targetClassId} class="sel">
              <option value="">Select class…</option>
              {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
            </select>
          </label>
          <label class="block">
            <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Target term</span>
            <select bind:value={targetTermId} class="sel">
              <option value="">Select term…</option>
              {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
            </select>
          </label>
        </div>

        {#if error}<p class="mt-3 text-xs text-red-500">{error}</p>{/if}
      </div>

      <div class="mt-6 flex shrink-0 justify-end gap-3 p-6 pt-0">
        <button onclick={closeModal}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
        <button onclick={confirm} disabled={$bulkMut.isPending}
          class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
          style="background: var(--brand)">
          {$bulkMut.isPending ? 'Processing…' : `${LABELS[action].title} ${count}`}
        </button>
      </div>
    </div>
  </div>
{/if}

<OverrideReasonModal
  open={overrideNeeded}
  title="Class mismatch"
  errorMessage={overrideError}
  isPending={$bulkMut.isPending}
  onSubmit={(reason) => $bulkMut.mutate(reason)}
  onCancel={() => { overrideNeeded = false; overrideError = ''; }}
/>

<style>
  @reference "tailwindcss";
  .sel { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

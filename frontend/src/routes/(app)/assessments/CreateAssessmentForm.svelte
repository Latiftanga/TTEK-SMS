<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createAssessment, formatAssessmentDate, type Assessment, type AssessmentType } from '$lib/api/assessments';
  import { detailOf, isLocked } from '$lib/apiError';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  interface Props {
    classId: string; subjectId: string; termId: string;
    types: AssessmentType[]; defaultTypeId: string;
    subjectLabel: string;
    onCreated: (a: Assessment) => void;
    onCancel: () => void;
  }
  const { classId, subjectId, termId, types, defaultTypeId, subjectLabel, onCreated, onCancel }: Props = $props();

  const qc = useQueryClient();
  let cf = $state({
    typeId: defaultTypeId || (types.length === 1 ? types[0].id : ''),
    description: '', maxScore: '100', dueDate: '',
  });
  let cfError = $state('');
  let lockOverride = $state(false);
  let lockOverrideError = $state('');

  const createMut = createMutation({
    mutationFn: (overrideReason: string | undefined) => createAssessment({
      class_id: classId, subject_id: subjectId,
      assessment_type_id: cf.typeId, academic_term_id: termId,
      description: cf.description.trim() || undefined, max_score: parseFloat(cf.maxScore),
      due_date: cf.dueDate || undefined,
    }, overrideReason),
    onSuccess: (a: Assessment) => {
      lockOverride = false; lockOverrideError = '';
      qc.invalidateQueries({ queryKey: ['assessments', classId, termId] });
      onCreated(a);
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { lockOverride = true; lockOverrideError = detailOf(e) ?? 'This term is locked.'; return; }
      cfError = detailOf(e) ?? 'Could not create.';
    },
  });

  function handleCreate() {
    cfError = '';
    if (!cf.typeId) { cfError = 'Choose a type for this assessment.'; return; }
    const score = parseFloat(cf.maxScore);
    if (isNaN(score) || score <= 0) { cfError = 'Enter a valid max score.'; return; }
    $createMut.mutate(undefined);
  }
</script>

<div class="mt-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
  <p class="mb-1 text-sm font-semibold text-[var(--fg)]">New assessment</p>
  <!-- Subject isn't asked here — it's already the page's own filter (the
       form can't even open without it set), so re-asking would just be the
       same choice made twice. Type IS asked, since it's just a filter on the
       list now, not a page-level gate — pre-filled from the list's current
       filter pill, if one is selected. -->
  <p class="mb-3 text-xs text-[var(--fg-subtle)]">
    {subjectLabel} — recorded as today, {formatAssessmentDate(new Date().toISOString())}
  </p>
  <div class="grid gap-3 sm:grid-cols-2">
    <div class="sm:col-span-2">
      <label for="cf-type" class="label">Type <span class="text-red-500">*</span></label>
      <select id="cf-type" bind:value={cf.typeId} class="input">
        <option value="">Select type…</option>
        {#each types as t (t.id)}<option value={t.id}>{t.name}</option>{/each}
      </select>
    </div>
    <div><label for="cf-due" class="label">Date given to students</label><input id="cf-due" type="date" bind:value={cf.dueDate} class="input" /></div>
    <div><label for="cf-max" class="label">Max score <span class="text-red-500">*</span></label><input id="cf-max" type="number" min="1" step="0.5" inputmode="decimal" bind:value={cf.maxScore} class="input" /></div>
    <div class="sm:col-span-2"><label for="cf-desc" class="label">Description (optional)</label><input id="cf-desc" bind:value={cf.description} placeholder="e.g. Covers chapters 3–4" class="input" /></div>
  </div>
  {#if cfError}<p class="mt-2 text-xs text-red-500">{cfError}</p>{/if}
  <div class="mt-3 flex gap-2">
    <button onclick={handleCreate} disabled={$createMut.isPending}
      class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
      {$createMut.isPending ? 'Creating…' : 'Create & open'}
    </button>
    <button onclick={onCancel}
      class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
  </div>
</div>

<OverrideReasonModal
  open={lockOverride}
  errorMessage={lockOverrideError}
  isPending={$createMut.isPending}
  onSubmit={(reason) => $createMut.mutate(reason)}
  onCancel={() => { lockOverride = false; lockOverrideError = ''; }}
/>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listAssessmentTypes, createAssessmentType, updateAssessmentType, deleteAssessmentType, listTypePresets,
    type AssessmentType,
  } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import AssessmentTypeForm, { type AssessmentTypeFormState } from './AssessmentTypeForm.svelte';
  import TypeRow from './TypeRow.svelte';

  const qc = useQueryClient();
  setPageTitle('Assessment Types');

  const typesQ = createQuery({
    queryKey: ['assessment-types'],
    queryFn:  listAssessmentTypes,
    staleTime: 5 * 60_000,
  });

  const presetsQ = createQuery({
    queryKey: ['assessment-type-presets'],
    queryFn:  listTypePresets,
    staleTime: Infinity,
  });
  const wacGesPreset = $derived($presetsQ.data?.waec_ges_shs ?? []);

  // Diagnostic types never enter a term total (excluded at the query level
  // in report_card.py::_load_scores()/report_card_rank.py/transcript.py) —
  // their weight is inert, so counting it here would either force real
  // graded types to under-allocate to make phantom room for it, or show a
  // permanently-confusing "≠100%" even when the real graded weights already
  // sum correctly. An inactive type's weight is equally inert — it can't be
  // used on a new assessment (create_assessment rejects it) — so it's
  // excluded the same way. The list itself still includes inactive types
  // (list_assessment_types) so this page can find and reactivate one.
  const totalWeight = $derived(
    ($typesQ.data ?? [])
      .filter(t => t.category !== 'DIAGNOSTIC' && t.is_active)
      .reduce((sum, t) => sum + Number(t.weight), 0)
  );
  const weightOk = $derived(Math.abs(totalWeight - 100) < 0.01);
  const hasDiagnostic = $derived(($typesQ.data ?? []).some(t => t.category === 'DIAGNOSTIC' && t.is_active));

  const emptyForm = (): AssessmentTypeFormState => ({
    name: '', code: '', weight: '',
    category: 'FORMATIVE',
    allow_multiple_entries: true, aggregation_strategy: 'SUM_NORMALIZE',
  });

  // ── Create form ───────────────────────────────────────────────────────────────
  let showForm  = $state(false);
  let form = $state(emptyForm());
  let formError = $state('');

  const createMut = createMutation({
    mutationFn: () => createAssessmentType({
      name: form.name.trim(),
      code: form.code.trim().toUpperCase(),
      weight: parseFloat(form.weight),
      category: form.category,
      allow_multiple_entries: form.allow_multiple_entries,
      aggregation_strategy: form.aggregation_strategy,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessment-types'] });
      showForm = false; formError = '';
      form = emptyForm();
      toast.success('Assessment type created.');
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create.';
    },
  });

  function handleCreate() {
    formError = '';
    if (!form.name.trim()) { formError = 'Name is required.'; return; }
    if (!form.code.trim()) { formError = 'Code is required.'; return; }
    const w = parseFloat(form.weight);
    if (isNaN(w) || w <= 0 || w > 100) { formError = 'Weight must be between 0.01 and 100.'; return; }
    $createMut.mutate();
  }

  // ── Inline edit ───────────────────────────────────────────────────────────────
  let editingId  = $state<string | null>(null);
  let editForm   = $state(emptyForm());
  let editError  = $state('');

  function toggleEdit(t: AssessmentType) {
    if (editingId === t.id) { editingId = null; return; }
    editingId = t.id;
    editForm  = {
      name: t.name, code: t.code, weight: String(t.weight),
      category: t.category,
      allow_multiple_entries: t.allow_multiple_entries, aggregation_strategy: t.aggregation_strategy,
    };
    editError = '';
    showForm  = false;
  }

  const updateMut = createMutation({
    mutationFn: (id: string) => updateAssessmentType(id, {
      name:   editForm.name.trim(),
      code:   editForm.code.trim().toUpperCase(),
      weight: parseFloat(editForm.weight),
      category: editForm.category,
      allow_multiple_entries: editForm.allow_multiple_entries,
      aggregation_strategy: editForm.aggregation_strategy,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessment-types'] });
      editingId = null; editError = '';
      toast.success('Assessment type updated.');
    },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.';
    },
  });

  function handleUpdate(id: string) {
    editError = '';
    if (!editForm.name.trim()) { editError = 'Name is required.'; return; }
    if (!editForm.code.trim()) { editError = 'Code is required.'; return; }
    const w = parseFloat(editForm.weight);
    if (isNaN(w) || w <= 0 || w > 100) { editError = 'Weight must be between 0.01 and 100.'; return; }
    $updateMut.mutate(id);
  }

  // ── Deactivate / reactivate ──────────────────────────────────────────────────
  // Reactivating needs no confirmation (purely additive, un-hides the type);
  // deactivating does, mirroring SubjectsTab.svelte's established pattern.
  let confirmDeactivate = $state<{ id: string; name: string } | null>(null);

  const toggleActiveMut = createMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => updateAssessmentType(id, { is_active }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['assessment-types'] });
      confirmDeactivate = null;
      toast.success(vars.is_active ? 'Assessment type reactivated.' : 'Assessment type deactivated.');
    },
    onError: () => { confirmDeactivate = null; toast.error('Could not update status.'); },
  });

  // ── Delete ────────────────────────────────────────────────────────────────────
  // Hard delete only ever succeeds server-side when zero assessments
  // reference the type — a 409 (real data exists) surfaces its own message
  // pointing at Deactivate instead, rather than a generic failure toast.
  let confirmDelete = $state<{ id: string; name: string } | null>(null);

  const deleteMut = createMutation({
    mutationFn: (id: string) => deleteAssessmentType(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessment-types'] });
      confirmDelete = null;
      toast.success('Assessment type deleted.');
    },
    onError: (e: unknown) => {
      confirmDelete = null;
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? 'Could not delete.');
    },
  });
</script>

<PageHeader title="Assessment Types" description="Define categories like class tests, exams, and projects. Weights must sum to 100." />

<div class="mb-4 flex items-center justify-end gap-2">
  {#if ($typesQ.data ?? []).length > 0}
    <div class="flex flex-col items-end gap-0.5">
      <span class="rounded-full px-2.5 py-0.5 text-[10px] font-bold ring-1 ring-inset
        {weightOk
          ? 'bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/30 dark:text-green-400'
          : 'bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400'}">
        Formative + Summative: {totalWeight.toFixed(2)}%{weightOk ? ' ✓' : ' ≠ 100'}
      </span>
      {#if hasDiagnostic}
        <span class="text-[10px] text-[var(--fg-subtle)]">Diagnostic isn't graded, so it doesn't count toward this total.</span>
      {/if}
    </div>
  {/if}
  <button onclick={() => { showForm = !showForm; formError = ''; editingId = null; }}
    class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
    style="background: var(--brand)">
    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
    Add type
  </button>
</div>

{#if showForm}
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <AssessmentTypeForm
      form={form}
      onChange={patch => form = { ...form, ...patch }}
      error={formError}
      pending={$createMut.isPending}
      onSubmit={handleCreate}
      onCancel={() => { showForm = false; formError = ''; }}
      submitLabel="Create"
      presets={wacGesPreset}
    />
  </div>
{/if}

{#if $typesQ.isPending}
  <div class="space-y-2">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if ($typesQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No assessment types defined yet.</p>
  </div>
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <table class="w-full text-sm">
      <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-3">Name</th>
        <th class="px-4 py-3">Code</th>
        <th class="px-4 py-3">Category</th>
        <th class="px-4 py-3 text-right">Weight</th>
        <th class="px-4 py-3">Status</th>
        <th class="px-4 py-3"></th>
      </tr></thead>
      <tbody>
        {#each $typesQ.data ?? [] as t (t.id)}
          <TypeRow
            {t}
            isEditing={editingId === t.id}
            {editForm}
            {editError}
            updatePending={$updateMut.isPending}
            toggleActivePending={$toggleActiveMut.isPending}
            deletePending={$deleteMut.isPending}
            onToggleEdit={toggleEdit}
            onEditFormChange={patch => editForm = { ...editForm, ...patch }}
            onSaveEdit={() => handleUpdate(t.id)}
            onCancelEdit={() => { editingId = null; editError = ''; }}
            onToggleActive={tt => tt.is_active ? (confirmDeactivate = { id: tt.id, name: tt.name }) : $toggleActiveMut.mutate({ id: tt.id, is_active: true })}
            onRequestDelete={tt => confirmDelete = { id: tt.id, name: tt.name }}
          />
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<ConfirmModal
  open={!!confirmDeactivate}
  title="Deactivate {confirmDeactivate?.name ?? 'assessment type'}?"
  message="This type will be hidden from new assessments. You can reactivate it at any time."
  confirmLabel="Deactivate"
  variant="warning"
  isPending={$toggleActiveMut.isPending}
  onConfirm={() => $toggleActiveMut.mutate({ id: confirmDeactivate!.id, is_active: false })}
  onCancel={() => confirmDeactivate = null}
/>

<ConfirmModal
  open={!!confirmDelete}
  title="Delete {confirmDelete?.name ?? 'assessment type'}?"
  message="This permanently removes the type. Only possible when no assessments have been recorded against it — if any exist, deactivate it instead."
  confirmLabel="Delete"
  variant="danger"
  isPending={$deleteMut.isPending}
  onConfirm={() => $deleteMut.mutate(confirmDelete!.id)}
  onCancel={() => confirmDelete = null}
/>

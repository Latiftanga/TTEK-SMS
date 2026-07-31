<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import {
    listSubjectRegistrations, registerSubjects, removeSubjectRegistration,
    type TermEnrollmentRead,
  } from '$lib/api/students';
  import { listClassSubjects, listSubjects, listAllTerms, listSubjectTeachers, type Subject } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';
  import { school } from '$lib/stores/school';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  interface Props {
    enrollment: TermEnrollmentRead;
    compact?: boolean;
  }
  const { enrollment, compact = false }: Props = $props();

  // Core/Elective is an SHS-programme concept — Basic schools follow a fixed
  // GES curriculum with no per-student subject choice, so the toggle and
  // badge would just be confusing jargon. Every registration still defaults
  // to CORE under the hood; this only hides the UI, same gate as
  // SubjectsTab.svelte's Core/Elective toggle.
  const showElectiveConcept = $derived($school?.schoolType !== 'BASIC');

  const qc = useQueryClient();
  let showAddForm = $state(false);
  let subjectId   = $state('');
  let regType     = $state<'CORE' | 'ELECTIVE'>('CORE');
  let addError    = $state('');
  let addOverrideNeeded = $state(false);

  let removeTarget = $state<string | null>(null);
  let removeOverrideNeeded = $state(false);
  let removeError = $state('');

  function isLocked(e: unknown): boolean {
    return (e as { response?: { status?: number } })?.response?.status === 423;
  }
  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }

  const subjectRegsQ = createQuery({
    queryKey: ['term-subject-regs', enrollment.id],
    queryFn:  () => listSubjectRegistrations(enrollment.id),
    staleTime: 60_000,
  });

  const allSubjectsQ = createQuery({
    queryKey: ['subjects'],
    queryFn:  listSubjects,
    staleTime: 5 * 60_000,
  });

  const classSubjectsQ = createQuery({
    queryKey: ['class-subjects', enrollment.class_id],
    queryFn:  () => enrollment.class_id ? listClassSubjects(enrollment.class_id) : Promise.resolve([]),
    enabled:  () => !!enrollment.class_id,
    staleTime: 5 * 60_000,
  });

  // Teacher-assignment awareness — informational only, never blocks
  // registration (a school may set up curriculum before a teacher is hired).
  // SubjectTeacher is year-scoped, not term-scoped, so resolve the year that
  // contains this enrollment's term rather than assuming "current".
  const allTermsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const yearId = $derived(($allTermsQ.data ?? []).find(t => t.id === enrollment.academic_term_id)?.academic_year_id ?? '');

  // Writable store pattern — keeps queryFn/enabled reactive to yearId (which
  // starts empty until allTermsQ resolves), mirroring SubjectsTab.svelte's
  // subjTeachersOpts / SubjectRosterPanel.svelte's rosterOpts.
  const subjTeachersOpts = writable({
    queryKey: ['subject-teachers', enrollment.class_id, ''] as (string | null)[],
    queryFn: () => listSubjectTeachers(enrollment.class_id!, ''),
    enabled: false,
    staleTime: 60_000,
  });
  $effect(() => {
    const y = yearId;
    subjTeachersOpts.set({
      queryKey: ['subject-teachers', enrollment.class_id, y],
      queryFn: () => listSubjectTeachers(enrollment.class_id!, y),
      enabled: !!enrollment.class_id && !!y,
      staleTime: 60_000,
    });
  });
  const subjTeachersQ = createQuery(subjTeachersOpts);
  const subjectsWithTeacher = $derived(new Set(($subjTeachersQ.data ?? []).map(st => st.subject_id)));

  const registeredIds = $derived(new Set(($subjectRegsQ.data ?? []).map(r => r.subject_id)));

  const availableSubjects = $derived.by<Subject[]>(() => {
    const all = $allSubjectsQ.data ?? [];
    const cls = $classSubjectsQ.data;
    if (cls && cls.length > 0) {
      return cls
        .filter(cs => !registeredIds.has(cs.subject_id))
        .map(cs => all.find(s => s.id === cs.subject_id))
        .filter((s): s is Subject => !!s);
    }
    return all.filter(s => !registeredIds.has(s.id));
  });

  const subjectName = (id: string) =>
    ($allSubjectsQ.data ?? []).find(s => s.id === id)?.name ?? '—';

  const addMut = createMutation({
    mutationFn: (overrideReason: string | undefined) =>
      registerSubjects(enrollment.id, [{ subject_id: subjectId, registration_type: regType }], overrideReason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['term-subject-regs', enrollment.id] });
      subjectId = ''; regType = 'CORE'; addError = ''; addOverrideNeeded = false; showAddForm = false;
      toast.success('Subject added.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { addOverrideNeeded = true; addError = detailOf(e) ?? 'This term is locked.'; return; }
      addError = detailOf(e) ?? 'Could not add subject.';
    },
  });

  function handleAdd() {
    addError = '';
    if (!subjectId) { addError = 'Select a subject.'; return; }
    $addMut.mutate(undefined);
  }

  function closeForm() { showAddForm = false; subjectId = ''; addError = ''; addOverrideNeeded = false; }

  const removeMut = createMutation({
    mutationFn: (overrideReason: string | undefined) => removeSubjectRegistration(enrollment.id, removeTarget!, overrideReason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['term-subject-regs', enrollment.id] });
      removeTarget = null; removeOverrideNeeded = false; removeError = '';
      toast.success('Subject removed.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { removeOverrideNeeded = true; removeError = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error(detailOf(e) ?? 'Could not remove subject.');
      removeTarget = null;
    },
  });

  function handleRemove(regId: string) {
    removeTarget = regId;
    $removeMut.mutate(undefined);
  }
</script>

<div class="flex items-center justify-between {compact ? 'pt-1' : ''}">
  <p class="text-xs font-semibold {compact ? '' : 'uppercase'} tracking-wide text-[var(--fg-muted)]">
    Subject Registration
    {#if !$subjectRegsQ.isPending}
      <span class="ml-1 font-normal {compact ? '' : 'normal-case'} text-[var(--fg-muted)]">
        · {($subjectRegsQ.data ?? []).length} registered
      </span>
    {/if}
  </p>
  {#if !showAddForm && !$allSubjectsQ.isPending}
    <button onclick={() => showAddForm = true}
      class="rounded-lg {compact ? 'px-2.5' : 'px-3'} py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      + Add subject
    </button>
  {/if}
</div>

{#if showAddForm}
  <div class="space-y-2.5 {compact ? 'py-2' : 'mt-3 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3'}">
    <select bind:value={subjectId} class="sel w-full">
      <option value="">Select subject…</option>
      {#each availableSubjects as s}
        <option value={s.id}>{s.name}{(!$subjTeachersQ.isPending && !subjectsWithTeacher.has(s.id)) ? ' (no teacher assigned)' : ''}</option>
      {/each}
      {#if availableSubjects.length === 0 && !$allSubjectsQ.isPending}
        <option disabled>All subjects registered</option>
      {/if}
    </select>

    <!-- Core / Elective toggle (SHS-only — Basic has no per-student subject choice) -->
    {#if showElectiveConcept}
      <div class="flex overflow-hidden rounded-lg border border-[var(--border)]">
        <button type="button" onclick={() => regType = 'CORE'}
          class="flex-1 py-1.5 text-xs font-semibold transition
            {regType === 'CORE' ? 'text-white' : 'bg-[var(--bg)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}"
          style={regType === 'CORE' ? 'background: var(--brand)' : ''}>
          Core
        </button>
        <button type="button" onclick={() => regType = 'ELECTIVE'}
          class="flex-1 border-l border-[var(--border)] py-1.5 text-xs font-semibold transition
            {regType === 'ELECTIVE' ? 'text-white' : 'bg-[var(--bg)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}"
          style={regType === 'ELECTIVE' ? 'background: var(--brand)' : ''}>
          Elective
        </button>
      </div>
    {/if}

    {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}

    <div class="flex items-center gap-3">
      <button onclick={handleAdd} disabled={$addMut.isPending || !subjectId}
        class="rounded-lg px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-40 transition hover:opacity-90"
        style="background: var(--brand)">
        {$addMut.isPending ? 'Adding…' : 'Add subject'}
      </button>
      <button onclick={closeForm} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
        Cancel
      </button>
    </div>
  </div>
{/if}

{#if $subjectRegsQ.isPending}
  {#each [1, 2] as _}
    <div class="mt-2 h-7 animate-pulse rounded-lg bg-[var(--hover)]"></div>
  {/each}
{:else if ($subjectRegsQ.data ?? []).length === 0 && !showAddForm}
  <p class="mt-2 text-xs text-[var(--fg-muted)]">No subjects registered yet.</p>
{:else}
  {#each $subjectRegsQ.data ?? [] as reg (reg.id)}
    <div class="flex items-center justify-between py-1 group">
      <span class="text-sm text-[var(--fg)]">{subjectName(reg.subject_id)}</span>
      <div class="flex items-center gap-2">
        {#if !$subjTeachersQ.isPending && !subjectsWithTeacher.has(reg.subject_id)}
          <span class="text-amber-500" title="No teacher assigned to this subject yet">⚠</span>
        {/if}
        {#if showElectiveConcept}
          <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide {
            reg.registration_type === 'CORE'
              ? 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400'
              : 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400'
          }">{reg.registration_type === 'CORE' ? 'Core' : 'Elective'}</span>
        {/if}
        <button
          onclick={() => handleRemove(reg.id)}
          disabled={$removeMut.isPending && removeTarget === reg.id}
          class="rounded p-0.5 text-[var(--fg-subtle)] opacity-0 group-hover:opacity-100 transition
                 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-30"
          title="Remove subject">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>
  {/each}
{/if}

<OverrideReasonModal
  open={addOverrideNeeded || removeOverrideNeeded}
  errorMessage={addOverrideNeeded ? addError : removeError}
  isPending={addOverrideNeeded ? $addMut.isPending : $removeMut.isPending}
  message="This term's results are locked. Adding or removing a subject registration this late requires a reason — it is written to the audit log."
  onSubmit={(reason) => {
    if (addOverrideNeeded) $addMut.mutate(reason);
    else if (removeOverrideNeeded) $removeMut.mutate(reason);
  }}
  onCancel={() => {
    if (addOverrideNeeded) addOverrideNeeded = false;
    else { removeOverrideNeeded = false; removeTarget = null; }
  }}
/>

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

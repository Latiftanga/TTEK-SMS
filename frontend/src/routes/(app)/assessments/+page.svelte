<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { goto } from '$app/navigation';
  import {
    listAssessments, listAssessmentTypes, createAssessment, listMySubjects,
    type Assessment,
  } from '$lib/api/assessments';
  import { listYears, updateTerm } from '$lib/api/academic';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  setPageTitle('Assessments');

  const qc = useQueryClient();
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Filters ───────────────────────────────────────────────────────────────────
  let classId   = $state('');
  let termId    = $state('');
  let subjectId = $state('');

  const yearsQ   = createQuery({ queryKey: ['academic-years'],  queryFn: listYears,    staleTime: 5 * 60_000 });
  const typesQ   = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });

  const allTerms = $derived(
    ($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name })))
  );
  const selectedTerm = $derived(allTerms.find(t => t.id === termId));

  $effect(() => {
    const cur = allTerms.find(t => t.is_current);
    if (cur && !termId) termId = cur.id;
  });

  // (class, subject) combos the caller can create assessments/enter scores
  // for — scoped to their own SubjectTeacher assignment(s) unless they hold
  // assessments.approve_scores. Powers both the class picker and the create
  // form's subject picker, cascaded by the selected class.
  const mySubjectsQ = reactiveQuery(() => ({
    queryKey: ['my-subjects', termId] as const,
    queryFn:  () => listMySubjects(termId),
    enabled:  !!termId,
    staleTime: 5 * 60_000,
  }));

  const myClasses = $derived.by(() => {
    const seen = new Map<string, { id: string; display_name: string }>();
    for (const p of $mySubjectsQ.data ?? []) {
      if (!seen.has(p.class_id)) seen.set(p.class_id, { id: p.class_id, display_name: p.class_name });
    }
    return [...seen.values()].sort((a, b) => a.display_name.localeCompare(b.display_name));
  });

  // Subjects taught in the selected class — cascades from the Class picker,
  // replacing what used to be a plain class-name suffix with a real filter.
  // Powers both the list's Subject filter and the create form's Subject picker.
  const subjectsForClass = $derived(
    ($mySubjectsQ.data ?? []).filter(p => p.class_id === classId)
  );

  // Reset subject when the class changes — a subject from the previous class
  // must not silently linger and filter out everything in the new one.
  $effect(() => { classId; subjectId = ''; });

  // Auto-select subject when only one is taught in this class (mirrors the
  // class auto-select below for a teacher with a single prep there).
  $effect(() => {
    if (subjectsForClass.length === 1 && !subjectId) subjectId = subjectsForClass[0].subject_id;
  });

  const subjectName = (id: string) => subjectsForClass.find(p => p.subject_id === id)?.subject_name ?? '—';

  const resultsLockMut = createMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => updateTerm(id, { results_locked: on }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      qc.invalidateQueries({ queryKey: ['all-terms'] });
    },
  });

  // Auto-select class when only one is available (e.g. class teacher with one class)
  $effect(() => {
    if (myClasses.length === 1 && !classId) classId = myClasses[0].id;
  });

  const assessmentsQ = reactiveQuery(() => ({
    queryKey: ['assessments', classId, termId] as const,
    queryFn:  () => listAssessments(classId, termId),
    enabled:  !!(classId && termId),
    staleTime: 30_000,
  }));

  // The list endpoint is class+term scoped (already server-filtered to just
  // the caller's own subject(s) in that class); narrowing to one subject when
  // a class teaches more than one is a pure client-side filter on top — no
  // extra round trip, the data's already fully fetched and small.
  const visibleAssessments = $derived(
    subjectId ? ($assessmentsQ.data ?? []).filter(a => a.subject_id === subjectId) : ($assessmentsQ.data ?? [])
  );

  // ── Helpers ───────────────────────────────────────────────────────────────────
  const typeName = (id: string) => ($typesQ.data ?? []).find(t => t.id === id)?.name ?? '—';

  // ── Create form ───────────────────────────────────────────────────────────────
  let showCreate = $state(false);
  let cf = $state({ name: '', typeId: '', subjectId: '', maxScore: '100', dueDate: '' });
  let cfError = $state('');

  const createMut = createMutation({
    mutationFn: () => createAssessment({
      class_id: classId, subject_id: cf.subjectId,
      assessment_type_id: cf.typeId, academic_term_id: termId,
      name: cf.name.trim(), max_score: parseFloat(cf.maxScore),
      due_date: cf.dueDate || undefined,
    }),
    onSuccess: (a: Assessment) => {
      qc.invalidateQueries({ queryKey: ['assessments', classId, termId] });
      showCreate = false;
      cf = { name: '', typeId: '', subjectId: '', maxScore: '100', dueDate: '' };
      goto(`/assessments/${a.id}`);
    },
    onError: (e: unknown) => {
      cfError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create.';
    },
  });

  function handleCreate() {
    cfError = '';
    if (!cf.name.trim())  { cfError = 'Name is required.'; return; }
    if (!cf.typeId)       { cfError = 'Select an assessment type.'; return; }
    if (!cf.subjectId)    { cfError = 'Select a subject.'; return; }
    const score = parseFloat(cf.maxScore);
    if (isNaN(score) || score <= 0) { cfError = 'Enter a valid max score.'; return; }
    $createMut.mutate();
  }
</script>

<PageHeader title="Assessments" description="Enter scores, approve, and publish results by class and term." />

<!-- Filters -->
<div class="mb-5 flex flex-wrap items-end gap-3">
  <div class="flex-1 min-w-[160px]">
    <label for="f-class" class="label">Class</label>
    <select id="f-class" bind:value={classId} class="sel">
      <option value="">All classes…</option>
      {#each myClasses as c}<option value={c.id}>{c.display_name}</option>{/each}
    </select>
  </div>
  <div class="flex-1 min-w-[160px]">
    <label for="f-subject" class="label">Subject</label>
    <select id="f-subject" bind:value={subjectId} class="sel" disabled={!classId}>
      <option value="">{classId ? 'All subjects…' : 'Select a class first'}</option>
      {#each subjectsForClass as p}<option value={p.subject_id}>{p.subject_name}</option>{/each}
    </select>
  </div>
  {#if canManage}
    <!-- Admin/approver keep a real term picker — they legitimately browse past
         terms' assessments. A class/subject teacher is locked to the current
         term server-side (services/scoring.py::submit_scores), and the current
         term is already shown in the top bar, so no picker or label is shown
         to them here at all — replaced by the Subject filter above instead. -->
    <div class="flex-1 min-w-[180px]">
      <label for="f-term" class="label">Term</label>
      <select id="f-term" bind:value={termId} class="sel">
        <option value="">Select term…</option>
        {#each allTerms as t}<option value={t.id}>{t.yearName} — {t.name}</option>{/each}
      </select>
    </div>
  {/if}
  {#if canManage && termId && selectedTerm}
    <button
      onclick={() => $resultsLockMut.mutate({ id: termId, on: !selectedTerm.results_locked })}
      disabled={$resultsLockMut.isPending}
      title={selectedTerm.results_locked
        ? 'Unlock — scores and behaviour records for this term can be edited again'
        : 'Lock — freeze scores and behaviour records for this term (overridable with a reason)'}
      class="flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition disabled:opacity-50
        {selectedTerm.results_locked
          ? 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400'
          : 'border-[var(--border)] bg-[var(--card)] text-[var(--fg-muted)] hover:border-[var(--brand)] hover:text-[var(--brand)]'}">
      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        {#if selectedTerm.results_locked}
          <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 119 0v3.75M3.75 21.75h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
        {:else}
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
        {/if}
      </svg>
      {$resultsLockMut.isPending ? '…' : selectedTerm.results_locked ? 'Results locked' : 'Lock results'}
    </button>
  {/if}
  {#if canManage && classId && termId}
    <button onclick={() => { showCreate = !showCreate; cfError = ''; }}
      class="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      New assessment
    </button>
  {/if}
</div>

<!-- Create form -->
{#if showCreate}
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="mb-3 text-sm font-semibold text-[var(--fg)]">New assessment</p>
    <div class="grid gap-3 sm:grid-cols-2">
      <div class="sm:col-span-2"><label for="cf-name" class="label">Assessment name <span class="text-red-500">*</span></label><input id="cf-name" bind:value={cf.name} placeholder="e.g. Mid-term Maths" class="input" /></div>
      <div>
        <label for="cf-type" class="label">Type <span class="text-red-500">*</span></label>
        <select id="cf-type" bind:value={cf.typeId} class="input">
          <option value="">Select type…</option>
          {#each $typesQ.data ?? [] as t}<option value={t.id}>{t.name} ({t.code})</option>{/each}
        </select>
      </div>
      <div>
        <label for="cf-subj" class="label">Subject <span class="text-red-500">*</span></label>
        <select id="cf-subj" bind:value={cf.subjectId} class="input">
          <option value="">Select subject…</option>
          {#each subjectsForClass as p}<option value={p.subject_id}>{p.subject_name}</option>{/each}
        </select>
      </div>
      <div><label for="cf-max" class="label">Max score <span class="text-red-500">*</span></label><input id="cf-max" type="number" min="1" step="0.5" bind:value={cf.maxScore} class="input" /></div>
      <div><label for="cf-due" class="label">Due date</label><input id="cf-due" type="date" bind:value={cf.dueDate} class="input" /></div>
    </div>
    {#if cfError}<p class="mt-2 text-xs text-red-500">{cfError}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={handleCreate} disabled={$createMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$createMut.isPending ? 'Creating…' : 'Create & open'}
      </button>
      <button onclick={() => { showCreate = false; cfError = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
    </div>
  </div>
{/if}

<!-- Assessments list -->
{#if !classId || !termId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
    <svg class="mx-auto mb-3 h-10 w-10 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
    </svg>
    <p class="text-sm font-medium text-[var(--fg-muted)]">
      {!classId && !termId ? 'Select a class and term to view assessments'
       : !classId ? 'Select a class to continue'
       : 'Select a term to continue'}
    </p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Use the filters above to get started.</p>
  </div>
{:else if $assessmentsQ.isPending}
  <div class="space-y-2">
    {#each [1, 2, 3] as _}<div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}
  </div>
{:else if visibleAssessments.length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm font-medium text-[var(--fg-muted)]">
      {subjectId ? 'No assessments for this subject yet.' : 'No assessments yet.'}
    </p>
    {#if canManage}<p class="mt-1 text-xs text-[var(--fg-subtle)]">Click "New assessment" to create one.</p>{/if}
  </div>
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <table class="w-full text-sm">
      <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-3">Assessment</th>
        <th class="hidden px-4 py-3 sm:table-cell">Subject</th>
        <th class="hidden px-4 py-3 sm:table-cell">Type</th>
        <th class="px-4 py-3 text-right">Max</th>
        <th class="hidden px-4 py-3 sm:table-cell">Due</th>
        <th class="px-4 py-3">Status</th>
      </tr></thead>
      <tbody>
        {#each visibleAssessments as a (a.id)}
          <tr onclick={() => goto(`/assessments/${a.id}`)}
            class="cursor-pointer border-b border-[var(--border)] last:border-0 transition hover:bg-[var(--hover)]">
            <td class="px-4 py-3 font-medium text-[var(--fg)]">{a.name}</td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{subjectName(a.subject_id)}</td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{typeName(a.assessment_type_id)}</td>
            <td class="px-4 py-3 text-right font-mono text-[var(--fg-muted)]">{a.max_score}</td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{a.due_date ?? '—'}</td>
            <td class="px-4 py-3">
              {#if a.is_published}
                <span class="rounded-full bg-green-50 px-2.5 py-0.5 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Published</span>
              {:else}
                <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">Draft</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .input { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

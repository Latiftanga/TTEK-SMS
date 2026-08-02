<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    listAssessments, listAssessmentTypes, createAssessment, listMySubjects,
    formatAssessmentDate, type Assessment,
  } from '$lib/api/assessments';
  import { listYears, updateTerm } from '$lib/api/academic';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import AssessmentCardList from './AssessmentCardList.svelte';
  setPageTitle('Assessments');

  const qc = useQueryClient();
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Filters ───────────────────────────────────────────────────────────────────
  // Persisted in the URL (not plain $state) so that navigating to a specific
  // assessment and back — or the browser's own back button — lands you right
  // back on the same filtered view instead of an empty picker.
  const sp       = $derived($page.url.searchParams);
  const classId    = $derived(sp.get('class')    ?? '');
  const termId     = $derived(sp.get('term')     ?? '');
  const subjectId  = $derived(sp.get('subject')  ?? '');
  const categoryId = $derived(sp.get('category') ?? '');

  // Picking a class invalidates whatever subject/category were chosen for
  // the previous one; picking a subject invalidates the category the same
  // way (mirrors the existing class→subject cascade this page already had).
  const CASCADE_CLEARS: Record<string, string[]> = {
    class: ['subject', 'category'],
    subject: ['category'],
  };
  function setFilter(key: string, value: string) {
    const url = new URL($page.url);
    if (value) url.searchParams.set(key, value);
    else       url.searchParams.delete(key);
    for (const dependent of CASCADE_CLEARS[key] ?? []) url.searchParams.delete(dependent);
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  const yearsQ   = createQuery({ queryKey: ['academic-years'],  queryFn: listYears,    staleTime: 5 * 60_000 });
  const typesQ   = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });

  const allTerms = $derived(
    ($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name })))
  );
  const selectedTerm = $derived(allTerms.find(t => t.id === termId));

  $effect(() => {
    const cur = allTerms.find(t => t.is_current);
    if (cur && !termId) setFilter('term', cur.id);
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

  // Auto-select subject when only one is taught in this class (mirrors the
  // class auto-select below for a teacher with a single prep there).
  $effect(() => {
    if (subjectsForClass.length === 1 && !subjectId) setFilter('subject', subjectsForClass[0].subject_id);
  });

  const subjectName = (id: string) => subjectsForClass.find(p => p.subject_id === id)?.subject_name ?? '—';

  // Auto-select category when the school only has one defined — same
  // courtesy as the class/subject auto-selects above.
  $effect(() => {
    if (($typesQ.data ?? []).length === 1 && !categoryId) setFilter('category', $typesQ.data![0].id);
  });

  const resultsLockMut = createMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => updateTerm(id, { results_locked: on }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      qc.invalidateQueries({ queryKey: ['all-terms'] });
    },
  });

  // Auto-select class when only one is available (e.g. class teacher with one class)
  $effect(() => {
    if (myClasses.length === 1 && !classId) setFilter('class', myClasses[0].id);
  });

  const assessmentsQ = reactiveQuery(() => ({
    queryKey: ['assessments', classId, termId] as const,
    queryFn:  () => listAssessments(classId, termId),
    enabled:  !!(classId && termId),
    staleTime: 30_000,
  }));

  // The list endpoint is class+term scoped (already server-filtered to just
  // the caller's own subject(s) in that class); narrowing further by subject
  // and/or category (assessment type) is a pure client-side filter on top —
  // no extra round trip, the data's already fully fetched and small.
  const visibleAssessments = $derived(
    ($assessmentsQ.data ?? [])
      .filter(a => !subjectId  || a.subject_id === subjectId)
      .filter(a => !categoryId || a.assessment_type_id === categoryId)
  );

  // ── Helpers ───────────────────────────────────────────────────────────────────
  const typeName = (id: string) => ($typesQ.data ?? []).find(t => t.id === id)?.name ?? '—';

  // ── Create form ───────────────────────────────────────────────────────────────
  // Subject and Category are never asked for here — the form only ever
  // opens once both are already locked in by the page filters (see the
  // "Assessments list" gating below), so re-asking for them would just be
  // the same choice made twice.
  let showCreate = $state(false);
  let cf = $state({ description: '', maxScore: '100', dueDate: '' });
  let cfError = $state('');

  const createMut = createMutation({
    mutationFn: () => createAssessment({
      class_id: classId, subject_id: subjectId,
      assessment_type_id: categoryId, academic_term_id: termId,
      description: cf.description.trim() || undefined, max_score: parseFloat(cf.maxScore),
      due_date: cf.dueDate || undefined,
    }),
    onSuccess: (a: Assessment) => {
      qc.invalidateQueries({ queryKey: ['assessments', classId, termId] });
      showCreate = false;
      cf = { description: '', maxScore: '100', dueDate: '' };
      goto(`/assessments/${a.id}`);
    },
    onError: (e: unknown) => {
      cfError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create.';
    },
  });

  function handleCreate() {
    cfError = '';
    const score = parseFloat(cf.maxScore);
    if (isNaN(score) || score <= 0) { cfError = 'Enter a valid max score.'; return; }
    $createMut.mutate();
  }

  // Opens the create form — shared by the empty-state's "New assessment"
  // button and the card list's own trailing "New assessment" row.
  // Subject/Category are already the page's own filters by the time this
  // can ever be called.
  function openCreateForm() {
    cf = { description: '', maxScore: '100', dueDate: '' };
    cfError = '';
    showCreate = true;
  }
</script>

<PageHeader title="Assessments" description="Enter scores, approve, and publish results by class and term." />

<!-- Filters — a single stacked column on phones (Class → Subject → Category
     is a strict left-to-right dependency, so a 2-up grid was jumbling the
     read order); reverts to a wrapping row from sm: up where there's room
     to read them side by side. -->
<div class="mb-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
  <div class="sm:w-44">
    <label for="f-class" class="label">Class</label>
    <select id="f-class" value={classId} onchange={e => setFilter('class', e.currentTarget.value)} class="sel">
      <option value="">Select class…</option>
      {#each myClasses as c}<option value={c.id}>{c.display_name}</option>{/each}
    </select>
  </div>
  <div class="sm:w-44">
    <label for="f-subject" class="label">Subject</label>
    <select id="f-subject" value={subjectId} onchange={e => setFilter('subject', e.currentTarget.value)} class="sel" disabled={!classId}>
      <option value="">{classId ? 'Select subject…' : 'Select a class first'}</option>
      {#each subjectsForClass as p}<option value={p.subject_id}>{p.subject_name}</option>{/each}
    </select>
  </div>
  <div class="sm:w-44">
    <label for="f-category" class="label">Category</label>
    <select id="f-category" value={categoryId} onchange={e => setFilter('category', e.currentTarget.value)} class="sel" disabled={!subjectId}>
      <option value="">{subjectId ? 'Select category…' : 'Select a subject first'}</option>
      {#each $typesQ.data ?? [] as t}<option value={t.id}>{t.name}</option>{/each}
    </select>
  </div>
  {#if canManage}
    <!-- Admin/approver keep a real term picker — they legitimately browse past
         terms' assessments. A class/subject teacher is locked to the current
         term server-side (services/scoring.py::submit_scores), and the current
         term is already shown in the top bar, so no picker or label is shown
         to them here at all — replaced by the Subject filter above instead. -->
    <div class="sm:flex-1 sm:min-w-[180px]">
      <label for="f-term" class="label">Term</label>
      <select id="f-term" value={termId} onchange={e => setFilter('term', e.currentTarget.value)} class="sel">
        <option value="">Select term…</option>
        {#each allTerms as t}<option value={t.id}>{t.yearName} — {t.name}</option>{/each}
      </select>
    </div>
  {/if}
</div>

<!-- Actions — own row, separate from the filter grid so buttons don't fight
     the selects for space on a phone. -->
<div class="mb-5 flex flex-wrap items-center gap-2">
  {#if canManage && termId && selectedTerm}
    <button
      onclick={() => $resultsLockMut.mutate({ id: termId, on: !selectedTerm.results_locked })}
      disabled={$resultsLockMut.isPending}
      title={selectedTerm.results_locked
        ? 'Unlock — scores and behaviour records for this term can be edited again'
        : 'Lock — freeze scores and behaviour records for this term (overridable with a reason)'}
      class="flex min-h-[44px] items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition disabled:opacity-50
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
</div>

<!-- Create form -->
{#if showCreate}
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="mb-1 text-sm font-semibold text-[var(--fg)]">New assessment</p>
    <!-- Subject/Category aren't asked here — they're already the page's own
         filters (the form can't even open without both set), so re-asking
         would just be the same choice made twice. -->
    <p class="mb-3 text-xs text-[var(--fg-subtle)]">
      {subjectName(subjectId)} · <span class="font-medium text-[var(--fg-muted)]">{typeName(categoryId)}</span> — recorded as today, {formatAssessmentDate(new Date().toISOString())}
    </p>
    <div class="grid gap-3 sm:grid-cols-2">
      <div><label for="cf-due" class="label">Date given to students</label><input id="cf-due" type="date" bind:value={cf.dueDate} class="input" /></div>
      <div><label for="cf-max" class="label">Max score <span class="text-red-500">*</span></label><input id="cf-max" type="number" min="1" step="0.5" bind:value={cf.maxScore} class="input" /></div>
      <div class="sm:col-span-2"><label for="cf-desc" class="label">Description (optional)</label><input id="cf-desc" bind:value={cf.description} placeholder="e.g. Covers chapters 3–4" class="input" /></div>
    </div>
    {#if cfError}<p class="mt-2 text-xs text-red-500">{cfError}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={handleCreate} disabled={$createMut.isPending}
        class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$createMut.isPending ? 'Creating…' : 'Create & open'}
      </button>
      <button onclick={() => { showCreate = false; cfError = ''; }}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
    </div>
  </div>
{/if}

<!-- Assessments list — Class, Subject, and Category are all required (in
     that order) before anything renders, on every breakpoint. That's what
     lets the create form skip asking for Subject/Category itself: by the
     time it can open, the page filters have already pinned both down. -->
{#if !classId || !termId || !subjectId || !categoryId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
    <svg class="mx-auto mb-3 h-10 w-10 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
    </svg>
    <p class="text-sm font-medium text-[var(--fg-muted)]">
      {!classId    ? 'Select a class to view assessments'
       : !termId    ? 'Select a term to continue'
       : !subjectId ? 'Select a subject to continue'
       : 'Select a category to continue'}
    </p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Use the filters above to get started.</p>
  </div>
{:else if $assessmentsQ.isPending}
  <div class="space-y-2">
    {#each [1, 2, 3] as _}<div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}
  </div>
{:else if visibleAssessments.length === 0}
  <!-- Nothing to attach a "+" to yet — this is the one place a standalone
       create button belongs: right where the table would otherwise be, now
       that Subject/Category are already known. No button shows anywhere
       before this point — picking filters comes first, creating after. -->
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm font-medium text-[var(--fg-muted)]">No {typeName(categoryId)} recorded yet for this subject.</p>
    <button onclick={openCreateForm}
      class="mt-4 inline-flex min-h-[44px] items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      New assessment
    </button>
  </div>
{:else}
  <!-- Same tappable list on every breakpoint — no separate desktop grid.
       Tapping a card hands off to the single-assessment page for score
       entry; "back" naturally returns here, since there's no inline-editing
       state to reconcile on the way out (see the "spreadsheet is confusing"
       discussion — the previous split had desktop behaving differently from
       mobile for no real benefit). -->
  <AssessmentCardList assessments={visibleAssessments} {typeName} onCreate={openCreateForm} />
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  /* min-h-[44px] — WCAG 2.1 AAA / Apple HIG touch-target minimum, since most
     users hit this page on a phone. */
  .sel   { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .input { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

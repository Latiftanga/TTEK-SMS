<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { listAssessments, listAssessmentTypes, listMySubjects, type Assessment } from '$lib/api/assessments';
  import { listYears, listClasses } from '$lib/api/academic';
  import { findCurrentTerm } from '$lib/academicPeriod';
  import { userRole } from '$lib/stores/permissions';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import AssessmentCardList from './AssessmentCardList.svelte';
  import AssessmentFilterBar from './AssessmentFilterBar.svelte';
  import CreateAssessmentForm from './CreateAssessmentForm.svelte';
  import TermActionsRow from './TermActionsRow.svelte';
  import SubjectRegistrationBanner from './SubjectRegistrationBanner.svelte';
  setPageTitle('Assessments');

  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Filters ───────────────────────────────────────────────────────────────────
  // Persisted in the URL (not plain $state) so that navigating to a specific
  // assessment and back — or the browser's own back button — lands you right
  // back on the same filtered view instead of an empty picker.
  const sp       = $derived($page.url.searchParams);
  const classId    = $derived(sp.get('class')    ?? '');
  const termId     = $derived(sp.get('term')     ?? '');
  const subjectId  = $derived(sp.get('subject')  ?? '');
  // Type (assessment_type_id) — a filter on the already-visible list, not a
  // gate in front of it (see the empty-state condition below). Kept in the
  // URL for shareability/back-button parity like the other filters, but
  // nothing waits for it to be set.
  const typeFilterId = $derived(sp.get('type') ?? '');

  // Picking a class invalidates whatever subject was chosen for the previous
  // one. Type is independent of both (a plain filter on the list), so it's
  // deliberately not in this cascade.
  const CASCADE_CLEARS: Record<string, string[]> = {
    class: ['subject'],
  };
  function setFilter(key: string, value: string) {
    const url = new URL($page.url);
    if (value) url.searchParams.set(key, value);
    else       url.searchParams.delete(key);
    for (const dependent of CASCADE_CLEARS[key] ?? []) url.searchParams.delete(dependent);
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  // Sets class+subject together in one navigation — used by the combined
  // teacher picker below, so choosing "SHS 2 Business A — Economics" doesn't
  // round-trip through two separate URL updates.
  function setClassSubject(classIdVal: string, subjectIdVal: string) {
    const url = new URL($page.url);
    if (classIdVal)   url.searchParams.set('class', classIdVal);   else url.searchParams.delete('class');
    if (subjectIdVal) url.searchParams.set('subject', subjectIdVal); else url.searchParams.delete('subject');
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  const yearsQ   = createQuery({ queryKey: ['academic-years'],  queryFn: listYears,    staleTime: 5 * 60_000 });
  const typesQ   = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });

  const allTerms = $derived(($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name }))));
  const selectedTerm = $derived(allTerms.find(t => t.id === termId));

  $effect(() => {
    const cur = findCurrentTerm(allTerms);
    if (cur && !termId) setFilter('term', cur.id);
  });

  // (class, subject) combos the caller can create assessments/enter scores
  // for — scoped to their own SubjectTeacher assignment(s) unless they hold
  // assessments.approve_scores. Powers the combined Class & subject picker
  // for a teacher below.
  const mySubjectsQ = reactiveQuery(() => ({
    queryKey: ['my-subjects', termId] as const,
    queryFn:  () => listMySubjects(termId),
    enabled:  !!termId,
    staleTime: 5 * 60_000,
  }));

  // Admin/approver aren't scoped to their own teaching load — the Class
  // picker should show every class in the school, not just ones that
  // happen to already have a subject assigned (a brand-new class with no
  // subjects yet would otherwise silently vanish from the list, hiding
  // exactly the thing an admin most needs to notice and go fix).
  const allClassesQ = createQuery({
    queryKey: ['academic-classes'], queryFn: listClasses,
    staleTime: 5 * 60_000, enabled: () => canManage,
  });

  const myClasses = $derived.by(() => {
    if (!canManage) return [];
    return ($allClassesQ.data ?? [])
      .filter(c => c.is_active)
      .map(c => ({ id: c.id, display_name: c.display_name }))
      .sort((a, b) => a.display_name.localeCompare(b.display_name));
  });

  // Subjects taught in the selected class — cascades from the Class picker
  // (admin/approver only; a teacher uses the combined picker below instead).
  const subjectsForClass = $derived(
    ($mySubjectsQ.data ?? []).filter(p => p.class_id === classId)
  );

  const myClassSubjectPairs = $derived(
    [...($mySubjectsQ.data ?? [])].sort((a, b) =>
      a.class_name.localeCompare(b.class_name) || a.subject_name.localeCompare(b.subject_name)
    )
  );

  // Auto-select when a teacher has exactly one (class, subject) combo — same
  // courtesy admin gets below for a single-class school.
  $effect(() => {
    if (!canManage && myClassSubjectPairs.length === 1 && !classId) {
      const only = myClassSubjectPairs[0];
      setClassSubject(only.class_id, only.subject_id);
    }
  });

  // Auto-select subject when only one is taught in this class (admin/approver
  // Class→Subject cascade only).
  $effect(() => {
    if (canManage && subjectsForClass.length === 1 && !subjectId) setFilter('subject', subjectsForClass[0].subject_id);
  });

  const subjectName = (id: string) => subjectsForClass.find(p => p.subject_id === id)?.subject_name ?? '—';

  // This picker also powers the assessment-creation type field (in
  // CreateAssessmentForm) — a deactivated type shouldn't be offered for new
  // assessments (matches the backend's own atype.is_active guard in
  // create_assessment). typeName still resolves against the full list so an
  // existing assessment recorded under a now-deactivated type still shows a
  // real label, not "—".
  const activeTypes = $derived(($typesQ.data ?? []).filter(t => t.is_active));

  // Auto-select class when only one is available (admin/approver only — a
  // teacher's combined picker above already covers the single-combo case).
  $effect(() => {
    if (canManage && myClasses.length === 1 && !classId) setFilter('class', myClasses[0].id);
  });

  const assessmentsQ = reactiveQuery(() => ({
    queryKey: ['assessments', classId, termId] as const,
    queryFn:  () => listAssessments(classId, termId),
    enabled:  !!(classId && termId),
    staleTime: 30_000,
  }));

  // The list endpoint is class+term scoped (already server-filtered to just
  // the caller's own subject(s) in that class); narrowing further by subject
  // and/or type is a pure client-side filter on top — no extra round trip,
  // the data's already fully fetched and small.
  const subjectAssessments = $derived(
    ($assessmentsQ.data ?? []).filter(a => !subjectId || a.subject_id === subjectId)
  );
  const visibleAssessments = $derived(
    subjectAssessments.filter(a => !typeFilterId || a.assessment_type_id === typeFilterId)
  );

  // Only types that actually have at least one assessment recorded for this
  // subject — no point offering a filter pill for a type nothing uses here.
  const typesInUse = $derived(
    activeTypes.filter(t => subjectAssessments.some(a => a.assessment_type_id === t.id))
  );

  // ── Helpers ───────────────────────────────────────────────────────────────────
  const typeName = (id: string) => ($typesQ.data ?? []).find(t => t.id === id)?.name ?? '—';

  // Shown once Class/Subject/Term are picked — no longer waits on Type,
  // which is just a filter on the list now, not a gate in front of it.
  const showRegistrationNudge = $derived(!canManage && !!(classId && termId && subjectId));

  // ── Create form ───────────────────────────────────────────────────────────────
  // Subject is never asked for here — it's already the page's own filter (the
  // form can't even open without it set). Type IS asked, since it's no
  // longer pinned down by the page filters — defaults to whichever pill is
  // currently selected, if any.
  let showCreate = $state(false);

  function handleCreated(a: Assessment) {
    showCreate = false;
    goto(`/assessments/${a.id}`);
  }

  // Opens the create form — shared by the empty-state's "New assessment"
  // button and the card list's own trailing "New assessment" row.
  function openCreateForm() {
    showCreate = true;
  }
</script>

<PageHeader title="Assessments" description="Enter scores, approve, and publish results by class and term." />

<AssessmentFilterBar
  {canManage} {classId} {subjectId} {termId}
  {myClasses} {subjectsForClass} {myClassSubjectPairs} {allTerms}
  onSetFilter={setFilter} onSetClassSubject={setClassSubject}
/>

<TermActionsRow {canManage} {classId} {termId} {selectedTerm} />

<SubjectRegistrationBanner
  {classId} {subjectId} {termId}
  subjectName={subjectName(subjectId)}
  visible={showRegistrationNudge}
/>

<!-- Assessments list — Class, Subject, and Term are required before anything
     renders. Type is a filter pill row on top of the list, not a fourth
     gate — a teacher lands straight on everything they've recorded for this
     subject instead of having to guess a type first just to look. -->
{#if !classId || !termId || !subjectId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
    <svg class="mx-auto mb-3 h-10 w-10 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
    </svg>
    <p class="text-sm font-medium text-[var(--fg-muted)]">
      {!classId    ? (canManage ? 'Select a class to view assessments' : 'Select a class & subject to view assessments')
       : !termId    ? 'Select a term to continue'
       : 'Select a subject to continue'}
    </p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Use the filters above to get started.</p>
  </div>
{:else if $assessmentsQ.isPending}
  <div class="space-y-2">
    {#each [1, 2, 3] as _}<div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}
  </div>
{:else}
  {#if typesInUse.length > 1}
    <!-- Type filter — a quick way to narrow an already-visible list, not a
         precondition for seeing it. "All" always included first. -->
    <div class="mb-3 flex flex-wrap gap-1.5">
      <button onclick={() => setFilter('type', '')}
        class="min-h-[36px] rounded-full px-3 text-xs font-semibold transition {!typeFilterId ? 'text-white' : 'border border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--brand)] hover:text-[var(--brand)]'}"
        style={!typeFilterId ? 'background: var(--brand)' : ''}>
        All
      </button>
      {#each typesInUse as t (t.id)}
        <button onclick={() => setFilter('type', t.id)}
          class="min-h-[36px] rounded-full px-3 text-xs font-semibold transition {typeFilterId === t.id ? 'text-white' : 'border border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--brand)] hover:text-[var(--brand)]'}"
          style={typeFilterId === t.id ? 'background: var(--brand)' : ''}>
          {t.name}
        </button>
      {/each}
    </div>
  {/if}

  {#if visibleAssessments.length === 0}
    <!-- Nothing to attach a "+" to yet — this is the one place a standalone
         create button belongs: right where the table would otherwise be, now
         that Subject is already known. No button shows anywhere before this
         point — picking filters comes first, creating after. -->
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm font-medium text-[var(--fg-muted)]">
        {typeFilterId ? `No ${typeName(typeFilterId)} recorded yet for this subject.` : 'No assessments recorded yet for this subject.'}
      </p>
      {#if !showCreate}
        <button onclick={openCreateForm}
          class="mt-4 inline-flex min-h-[44px] items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background: var(--brand)">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          New assessment
        </button>
      {/if}
    </div>
  {:else}
    <!-- Same tappable list on every breakpoint — no separate desktop grid.
         Tapping a card hands off to the single-assessment page for score
         entry; "back" naturally returns here, since there's no inline-editing
         state to reconcile on the way out. -->
    <AssessmentCardList assessments={visibleAssessments} {typeName} onCreate={openCreateForm} creating={showCreate} />
  {/if}
{/if}

<!-- Create form — deliberately placed after the list, not before it: both
     places that open it (the empty-state button and the card list's own
     trailing row) sit at the bottom of the page, so the form should appear
     right where the tap happened instead of jumping to the top. -->
{#if showCreate}
  <CreateAssessmentForm
    {classId} {subjectId} {termId}
    types={activeTypes}
    defaultTypeId={typeFilterId}
    subjectLabel={subjectName(subjectId)}
    onCreated={handleCreated}
    onCancel={() => showCreate = false}
  />
{/if}

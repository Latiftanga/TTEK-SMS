<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { goto } from '$app/navigation';
  import {
    listAssessments, listAssessmentTypes, createAssessment,
    type Assessment,
  } from '$lib/api/assessments';
  import { listClasses, listYears, listSubjects } from '$lib/api/academic';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  setPageTitle('Assessments');

  const qc = useQueryClient();
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Filters ───────────────────────────────────────────────────────────────────
  let classId = $state('');
  let termId  = $state('');

  const classesQ = createQuery({ queryKey: ['classes'],         queryFn: listClasses,  staleTime: 5 * 60_000 });
  const yearsQ   = createQuery({ queryKey: ['academic-years'],  queryFn: listYears,    staleTime: 5 * 60_000 });
  const typesQ   = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });
  const subjectsQ = createQuery({ queryKey: ['subjects'],        queryFn: listSubjects, staleTime: 5 * 60_000 });

  const allTerms = $derived(
    ($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name })))
  );

  $effect(() => {
    const cur = allTerms.find(t => t.is_current);
    if (cur && !termId) termId = cur.id;
  });

  // Auto-select class when only one is available (e.g. class teacher with one class)
  $effect(() => {
    const classes = $classesQ.data ?? [];
    if (classes.length === 1 && !classId) classId = classes[0].id;
  });

  const listOpts = writable({
    queryKey: ['assessments', classId, termId] as const,
    queryFn: () => listAssessments(classId, termId),
    enabled: !!(classId && termId),
    staleTime: 30_000,
  });
  $effect(() => {
    const cid = classId, tid = termId;
    listOpts.set({ queryKey: ['assessments', cid, tid] as const, queryFn: () => listAssessments(cid, tid), enabled: !!(cid && tid), staleTime: 30_000 });
  });
  const assessmentsQ = createQuery(listOpts);

  // ── Helpers ───────────────────────────────────────────────────────────────────
  const typeName    = (id: string) => ($typesQ.data    ?? []).find(t => t.id === id)?.name ?? '—';
  const subjectName = (id: string) => ($subjectsQ.data ?? []).find(s => s.id === id)?.name ?? '—';

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
      {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
    </select>
  </div>
  <div class="flex-1 min-w-[180px]">
    <label for="f-term" class="label">Term</label>
    <select id="f-term" bind:value={termId} class="sel">
      <option value="">Select term…</option>
      {#each allTerms as t}<option value={t.id}>{t.yearName} — {t.name}</option>{/each}
    </select>
  </div>
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
          {#each $subjectsQ.data ?? [] as s}<option value={s.id}>{s.name}</option>{/each}
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
{:else if ($assessmentsQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm font-medium text-[var(--fg-muted)]">No assessments yet.</p>
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
        {#each $assessmentsQ.data ?? [] as a (a.id)}
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

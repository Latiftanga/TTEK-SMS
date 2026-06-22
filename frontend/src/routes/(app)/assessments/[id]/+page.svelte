<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    getAssessment, listScores, submitScores, approveScores,
    publishAssessment, updateAssessment, deleteAssessment,
    listAssessmentTypes, type Score,
  } from '$lib/api/assessments';
  import { listSubjects } from '$lib/api/academic';
  import { listStudents } from '$lib/api/students';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import ScoreTable from './ScoreTable.svelte';

  const qc = useQueryClient();
  const assessmentId   = $derived($page.params.id);
  const canManage      = $derived($userRole === 'admin' || $userRole === 'approver');
  const canEnterScores = $derived($userRole === 'teacher' || canManage);

  const assessmentQ = createQuery({ queryKey: ['assessment', assessmentId], queryFn: () => getAssessment(assessmentId), staleTime: 60_000 });
  const scoresQ     = createQuery({ queryKey: ['scores', assessmentId],     queryFn: () => listScores(assessmentId),     staleTime: 30_000 });
  const subjectsQ   = createQuery({ queryKey: ['subjects'],          queryFn: listSubjects,          staleTime: 5 * 60_000 });
  const typesQ      = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });

  const studentsOpts = writable({ queryKey: ['students-for-class', ''] as const, queryFn: () => listStudents({}), enabled: false, staleTime: 60_000 });
  $effect(() => {
    const cid = $assessmentQ.data?.class_id;
    if (cid) studentsOpts.set({ queryKey: ['students-for-class', cid] as const, queryFn: () => listStudents({ class_id: cid }), enabled: true, staleTime: 60_000 });
  });
  const studentsQ = createQuery(studentsOpts);

  const subjectName = (id: string) => ($subjectsQ.data ?? []).find(s => s.id === id)?.name ?? '—';
  const typeName    = (id: string) => ($typesQ.data    ?? []).find(t => t.id === id)?.name ?? '—';

  // ── Score input state ─────────────────────────────────────────────────────────

  let scoreInputs    = $state<Record<string, string>>({});
  let initializedFor = $state<string | null>(null);

  $effect(() => {
    if ($scoresQ.data && initializedFor !== assessmentId) {
      const init: Record<string, string> = {};
      for (const s of $scoresQ.data) init[s.student_id] = String(s.raw_score);
      scoreInputs = init; initializedFor = assessmentId;
    }
  });

  const scoreMap = $derived(new Map(($scoresQ.data ?? []).map((s: Score) => [s.student_id, s])));

  // ── Mutations ─────────────────────────────────────────────────────────────────

  const submitMut = createMutation({
    mutationFn: () => {
      const a = $assessmentQ.data!;
      const entries = ($studentsQ.data ?? [])
        .filter(s => scoreInputs[s.id]?.trim() !== '' && scoreInputs[s.id] !== undefined)
        .map(s => ({ student_id: s.id, raw_score: parseFloat(scoreInputs[s.id]) }));
      const invalid = entries.filter(e => isNaN(e.raw_score) || e.raw_score < 0 || e.raw_score > Number(a.max_score));
      if (invalid.length > 0) throw new Error(`${invalid.length} score(s) out of range 0–${a.max_score}.`);
      return submitScores(assessmentId, entries);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['scores', assessmentId] }); toast.success('Scores saved.'); },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : ((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save.')),
  });

  const approveMut = createMutation({
    mutationFn: () => approveScores(assessmentId, ($scoresQ.data ?? []).filter(s => !s.is_approved).map(s => s.id)),
    onSuccess: (a) => { qc.invalidateQueries({ queryKey: ['scores', assessmentId] }); toast.success(`${a.length} score(s) approved.`); },
    onError: () => toast.error('Could not approve scores.'),
  });

  let confirmPublish = $state(false);
  const publishMut = createMutation({
    mutationFn: () => publishAssessment(assessmentId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assessment', assessmentId] }); confirmPublish = false; toast.success('Published. Guardians notified.'); },
    onError: () => { confirmPublish = false; toast.error('Could not publish.'); },
  });

  let editing  = $state(false);
  let editForm = $state({ name: '', maxScore: '', dueDate: '' });
  let editErr  = $state('');
  function startEdit() {
    const a = $assessmentQ.data!;
    editForm = { name: a.name, maxScore: String(a.max_score), dueDate: a.due_date ?? '' };
    editErr = ''; editing = true;
  }
  const editMut = createMutation({
    mutationFn: () => updateAssessment(assessmentId, { name: editForm.name.trim() || undefined, max_score: parseFloat(editForm.maxScore) || undefined, due_date: editForm.dueDate || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assessment', assessmentId] }); editing = false; toast.success('Assessment updated.'); },
    onError: (e: unknown) => { editErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.'; },
  });

  let confirmDelete = $state(false);
  const deleteMut = createMutation({
    mutationFn: () => deleteAssessment(assessmentId),
    onSuccess: () => { goto('/assessments'); toast.success('Assessment deleted.'); },
    onError: () => toast.error('Could not delete assessment.'),
  });

  const unapprovedCount = $derived(($scoresQ.data ?? []).filter(s => !s.is_approved).length);
</script>

<button onclick={() => goto('/assessments')}
  class="mb-3 flex items-center gap-1 text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>
  </svg>
  All assessments
</button>

{#if $assessmentQ.isPending}
  <div class="h-28 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else if $assessmentQ.data}
  {@const a = $assessmentQ.data}

  <!-- Header card -->
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    {#if editing}
      <div class="space-y-3">
        <div class="grid gap-2 sm:grid-cols-3">
          <div class="sm:col-span-1"><label class="label">Name</label><input bind:value={editForm.name} class="input" /></div>
          <div><label class="label">Max score</label><input type="number" min="1" step="0.5" bind:value={editForm.maxScore} class="input" /></div>
          <div><label class="label">Due date</label><input type="date" bind:value={editForm.dueDate} class="input" /></div>
        </div>
        {#if editErr}<p class="text-xs text-red-500">{editErr}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:opacity-90 transition" style="background:var(--brand)">
            {$editMut.isPending ? 'Saving…' : 'Save changes'}
          </button>
          <button onclick={() => { editing = false; editErr = ''; }} class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
        </div>
      </div>
    {:else}
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 class="text-lg font-bold text-[var(--fg)]">{a.name}</h1>
          <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
            {subjectName(a.subject_id)} · {typeName(a.assessment_type_id)} · Max {a.max_score}
            {#if a.due_date}<span class="ml-1 text-[var(--fg-subtle)]">· Due {a.due_date}</span>{/if}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          {#if a.is_published}
            <span class="rounded-full bg-green-50 px-3 py-1 text-xs font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Published</span>
          {:else}
            {#if canManage}
              <button onclick={startEdit} title="Edit" class="rounded-lg p-1.5 text-[var(--fg-subtle)] hover:bg-[var(--hover)] hover:text-[var(--fg)] transition">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/></svg>
              </button>
              {#if confirmDelete}
                <span class="text-xs text-red-500">Delete? All scores lost.</span>
                <button onclick={() => $deleteMut.mutate()} disabled={$deleteMut.isPending} class="rounded-xl bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50 transition">{$deleteMut.isPending ? 'Deleting…' : 'Yes, delete'}</button>
                <button onclick={() => confirmDelete = false} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
              {:else}
                <button onclick={() => confirmDelete = true} class="rounded-xl border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-950/30 transition">Delete</button>
              {/if}
              {#if unapprovedCount > 0}
                <button onclick={() => $approveMut.mutate()} disabled={$approveMut.isPending} class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] disabled:opacity-50 transition">
                  {$approveMut.isPending ? 'Approving…' : `Approve ${unapprovedCount}`}
                </button>
              {/if}
              {#if confirmPublish}
                <span class="text-xs text-[var(--fg-muted)]">Publish? Cannot be undone.</span>
                <button onclick={() => $publishMut.mutate()} disabled={$publishMut.isPending} class="rounded-xl bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition">{$publishMut.isPending ? 'Publishing…' : 'Yes, publish'}</button>
                <button onclick={() => confirmPublish = false} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
              {:else}
                <button onclick={() => confirmPublish = true} class="rounded-xl bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 transition">Publish</button>
              {/if}
            {/if}
            {#if canEnterScores}
              <button onclick={() => $submitMut.mutate()} disabled={$submitMut.isPending} class="rounded-xl px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
                {$submitMut.isPending ? 'Saving…' : 'Save scores'}
              </button>
            {/if}
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- Score table -->
  {#if $studentsQ.isPending || $scoresQ.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($studentsQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No students assigned to this class.</p>
    </div>
  {:else}
    <ScoreTable
      assessment={a}
      students={$studentsQ.data ?? []}
      {scoreMap}
      bind:scoreInputs
      {canEnterScores}
      isPending={$submitMut.isPending}
      onSave={() => $submitMut.mutate()}
    />
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

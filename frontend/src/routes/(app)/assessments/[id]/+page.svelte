<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    getAssessment, listScores, submitScores, approveScores, publishAssessment,
    listAssessmentTypes, type Score,
  } from '$lib/api/assessments';
  import { listSubjects } from '$lib/api/academic';
  import { listStudents } from '$lib/api/students';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';

  const qc = useQueryClient();
  const assessmentId = $derived($page.params.id);
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Queries ───────────────────────────────────────────────────────────────────

  const assessmentQ = createQuery({
    queryKey: ['assessment', assessmentId],
    queryFn:  () => getAssessment(assessmentId),
    staleTime: 60_000,
  });

  const scoresQ = createQuery({
    queryKey: ['scores', assessmentId],
    queryFn:  () => listScores(assessmentId),
    staleTime: 30_000,
  });

  const subjectsQ = createQuery({ queryKey: ['subjects'],          queryFn: listSubjects,          staleTime: 5 * 60_000 });
  const typesQ    = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });

  const studentsOpts = writable({ queryKey: ['students-for-class', ''] as const, queryFn: () => listStudents({}), enabled: false, staleTime: 60_000 });
  $effect(() => {
    const cid = $assessmentQ.data?.class_id;
    if (cid) studentsOpts.set({ queryKey: ['students-for-class', cid] as const, queryFn: () => listStudents({ class_id: cid }), enabled: true, staleTime: 60_000 });
  });
  const studentsQ = createQuery(studentsOpts);

  // ── Helpers ───────────────────────────────────────────────────────────────────

  const subjectName = (id: string) => ($subjectsQ.data ?? []).find(s => s.id === id)?.name ?? '—';
  const typeName    = (id: string) => ($typesQ.data    ?? []).find(t => t.id === id)?.name ?? '—';

  // ── Score input state ─────────────────────────────────────────────────────────

  let scoreInputs  = $state<Record<string, string>>({});
  let initialized  = $state(false);

  $effect(() => {
    if ($scoresQ.data && !initialized) {
      const init: Record<string, string> = {};
      for (const s of $scoresQ.data) init[s.student_id] = String(s.raw_score);
      scoreInputs = init;
      initialized = true;
    }
  });

  const scoreMap = $derived(new Map(($scoresQ.data ?? []).map((s: Score) => [s.student_id, s])));

  // ── Mutations ─────────────────────────────────────────────────────────────────

  const submitMut = createMutation({
    mutationFn: () => {
      const a = $assessmentQ.data!;
      const entries = ($studentsQ.data ?? [])
        .filter(s => scoreInputs[s.id]?.trim() !== '' && scoreInputs[s.id] !== undefined)
        .map(s => ({ student_id: s.id, raw_score: parseFloat(scoreInputs[s.id]) }))
        .filter(e => !isNaN(e.raw_score) && e.raw_score >= 0 && e.raw_score <= Number(a.max_score));
      return submitScores(assessmentId, entries);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['scores', assessmentId] });
      toast.success('Scores saved.');
    },
    onError: (e: unknown) => {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save scores.');
    },
  });

  const approveMut = createMutation({
    mutationFn: () => {
      const ids = ($scoresQ.data ?? []).filter(s => !s.is_approved).map(s => s.id);
      return approveScores(assessmentId, ids);
    },
    onSuccess: (approved) => {
      qc.invalidateQueries({ queryKey: ['scores', assessmentId] });
      toast.success(`${approved.length} score(s) approved.`);
    },
    onError: () => toast.error('Could not approve scores.'),
  });

  let confirmPublish = $state(false);
  const publishMut = createMutation({
    mutationFn: () => publishAssessment(assessmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessment', assessmentId] });
      confirmPublish = false;
      toast.success('Assessment published. Guardians notified by SMS.');
    },
    onError: () => { confirmPublish = false; toast.error('Could not publish.'); },
  });

  const unapprovedCount = $derived(($scoresQ.data ?? []).filter(s => !s.is_approved).length);
</script>

<svelte:head>
  <title>{$assessmentQ.data?.name ?? 'Assessment'} — Scores</title>
</svelte:head>

<!-- Back link -->
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
            {#if unapprovedCount > 0}
              <button onclick={() => $approveMut.mutate()} disabled={$approveMut.isPending}
                class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                {$approveMut.isPending ? 'Approving…' : `Approve ${unapprovedCount}`}
              </button>
            {/if}
            {#if confirmPublish}
              <span class="text-xs text-[var(--fg-muted)]">Publish? This cannot be undone.</span>
              <button onclick={() => $publishMut.mutate()} disabled={$publishMut.isPending}
                class="rounded-xl bg-green-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-green-700 disabled:opacity-50">
                {$publishMut.isPending ? 'Publishing…' : 'Yes, publish'}
              </button>
              <button onclick={() => confirmPublish = false} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
            {:else}
              <button onclick={() => confirmPublish = true}
                class="rounded-xl bg-green-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-green-700">Publish</button>
            {/if}
          {/if}
          {#if !a.is_published}
            <button onclick={() => $submitMut.mutate()} disabled={$submitMut.isPending || a.is_published}
              class="rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background: var(--brand)">
              {$submitMut.isPending ? 'Saving…' : 'Save scores'}
            </button>
          {/if}
        {/if}
      </div>
    </div>
  </div>

  <!-- Score table -->
  {#if $studentsQ.isPending || $scoresQ.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($studentsQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No students assigned to this class.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
            <th class="px-4 py-3">Student</th>
            <th class="px-4 py-3 text-center">Score <span class="normal-case font-normal">/ {a.max_score}</span></th>
            <th class="hidden px-4 py-3 text-center sm:table-cell">Grade</th>
            <th class="px-4 py-3 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {#each $studentsQ.data ?? [] as student (student.id)}
            {@const existing = scoreMap.get(student.id)}
            <tr class="border-b border-[var(--border)] last:border-0">
              <td class="px-4 py-2.5">
                <p class="font-medium text-[var(--fg)]">{student.display_name}</p>
                <p class="text-[10px] font-mono text-[var(--fg-subtle)]">{student.admission_number}</p>
              </td>
              <td class="px-4 py-2.5 text-center">
                {#if a.is_published}
                  <span class="font-mono text-[var(--fg)]">{existing?.raw_score ?? '—'}</span>
                {:else}
                  <input
                    type="number" min="0" max={a.max_score} step="0.5"
                    bind:value={scoreInputs[student.id]}
                    placeholder="—"
                    class="w-20 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-center text-sm font-mono text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition"
                  />
                {/if}
              </td>
              <td class="hidden px-4 py-2.5 text-center sm:table-cell">
                {#if existing?.cached_grade_label}
                  <span class="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400">
                    {existing.cached_grade_label}
                  </span>
                {:else}
                  <span class="text-[var(--fg-subtle)]">—</span>
                {/if}
              </td>
              <td class="px-4 py-2.5 text-center">
                {#if !existing}
                  <span class="text-[10px] text-[var(--fg-subtle)]">Not entered</span>
                {:else if existing.is_approved}
                  <svg class="mx-auto h-4 w-4 text-green-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                {:else}
                  <span class="text-[10px] text-amber-600 dark:text-amber-400">Pending</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    {#if !a.is_published}
      <div class="mt-3 flex justify-end">
        <button onclick={() => $submitMut.mutate()} disabled={$submitMut.isPending}
          class="rounded-xl px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$submitMut.isPending ? 'Saving…' : 'Save scores'}
        </button>
      </div>
    {/if}
  {/if}
{/if}

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import {
    getAssessment, listScores, submitScores, approveScores,
    publishAssessment, updateAssessment, deleteAssessment,
    listAssessmentTypes, type Score,
  } from '$lib/api/assessments';
  import { listSubjects } from '$lib/api/academic';
  import { listStudents } from '$lib/api/students';
  import { userRole } from '$lib/stores/permissions';
  import { auth } from '$lib/stores/auth';
  import { queueWrite } from '$lib/offline/outbox';
  import { refreshOutboxCount } from '$lib/offline/sync';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import ScoreTable from './ScoreTable.svelte';

  const qc = useQueryClient();
  const assessmentId   = $derived($page.params.id!);
  const canManage      = $derived($userRole === 'admin' || $userRole === 'approver');
  const canEnterScores = $derived($userRole === 'teacher' || canManage);

  const assessmentQ = createQuery({ queryKey: ['assessment', assessmentId], queryFn: () => getAssessment(assessmentId), staleTime: 60_000 });
  const scoresQ     = createQuery({ queryKey: ['scores', assessmentId],     queryFn: () => listScores(assessmentId),     staleTime: 30_000 });
  const subjectsQ   = createQuery({ queryKey: ['subjects'],         queryFn: listSubjects,          staleTime: 5 * 60_000 });
  const typesQ      = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes,   staleTime: 5 * 60_000 });

  const studentsQ = reactiveQuery(() => {
    const cid = $assessmentQ.data?.class_id ?? '';
    return {
      queryKey: ['students-for-class', cid] as const,
      queryFn:  () => listStudents({ class_id: cid }),
      enabled:  !!cid,
      staleTime: 60_000,
    };
  });

  const subjectName = (id: string) => ($subjectsQ.data ?? []).find(s => s.id === id)?.name ?? '—';
  const typeName    = (id: string) => ($typesQ.data    ?? []).find(t => t.id === id)?.name ?? '—';

  // ── Score inputs ──────────────────────────────────────────────────────────────
  let scoreInputs    = $state<Record<string, string | number>>({});
  let initializedFor = $state<string | null>(null);

  $effect(() => {
    if ($scoresQ.data && initializedFor !== assessmentId) {
      const init: Record<string, number> = {};
      for (const s of $scoresQ.data) init[s.student_id] = Number(s.raw_score);
      scoreInputs = init; initializedFor = assessmentId;
    }
  });

  const scoreMap = $derived(new Map(($scoresQ.data ?? []).map((s: Score) => [s.student_id, s])));
  const unapprovedCount = $derived(($scoresQ.data ?? []).filter(s => !s.is_approved).length);

  // ── Offline queue helper ──────────────────────────────────────────────────────
  async function queueScoresOffline(asmtId: string, entries: { student_id: string; raw_score: number }[]): Promise<void> {
    const schoolId = get(auth).schoolId ?? '';
    const osa = auth.offlineSessionStartedAt ?? new Date().toISOString();
    for (const e of entries) {
      await queueWrite({ entity: 'Score', method: 'POST', endpoint: `/assessments/${asmtId}/scores`,
        payload: { assessment_id: asmtId, student_id: e.student_id, raw_score: e.raw_score },
        offline_session_started_at: osa, school_id: schoolId });
    }
    await refreshOutboxCount();
  }

  // ── Mutations ─────────────────────────────────────────────────────────────────
  const submitMut = createMutation({
    mutationFn: async () => {
      const a = $assessmentQ.data!;
      const entries = ($studentsQ.data ?? [])
        .filter(s => scoreInputs[s.id] != null && scoreInputs[s.id] !== '')
        .map(s => ({ student_id: s.id, raw_score: Number(scoreInputs[s.id]) }));
      const invalid = entries.filter(e => isNaN(e.raw_score) || e.raw_score < 0 || e.raw_score > Number(a.max_score));
      if (invalid.length > 0) throw new Error(`${invalid.length} score(s) out of range 0–${a.max_score}.`);
      try {
        return { saved: await submitScores(assessmentId, entries), entries };
      } catch (err: unknown) {
        // No response → network unreachable; queue for later sync.
        if (!(err as { response?: unknown }).response) {
          await queueScoresOffline(assessmentId, entries);
          return { saved: null, entries };
        }
        throw err;
      }
    },
    onSuccess: ({ saved, entries }) => {
      if (!saved) {
        // Optimistically update cache so ScoreTable shows "All saved".
        const now = new Date().toISOString();
        qc.setQueryData(['scores', assessmentId], (old: Score[] | undefined) => [
          ...(old ?? []).filter(s => !entries.some(e => e.student_id === s.student_id)),
          ...entries.map(e => ({ id: `offline-${e.student_id}`, student_id: e.student_id,
            raw_score: String(e.raw_score), is_approved: false, cached_grade_label: null, submitted_at: now })),
        ] as Score[]);
        initializedFor = assessmentId;
        toast.info('No connection — scores queued and will sync when you reconnect.');
        return;
      }
      qc.invalidateQueries({ queryKey: ['scores', assessmentId] });
      const m = new Map(saved.map((s: Score) => [s.student_id, s]));
      const next: Record<string, string | number> = {};
      for (const s of $studentsQ.data ?? []) next[s.id] = m.get(s.id) ? Number(m.get(s.id)!.raw_score) : (scoreInputs[s.id] ?? '');
      scoreInputs = next; initializedFor = assessmentId;
      toast.success('Scores saved.');
    },
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : ((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save.')),
  });

  const approveMut = createMutation({
    mutationFn: () => approveScores(assessmentId, ($scoresQ.data ?? []).filter(s => !s.is_approved).map(s => s.id)),
    onSuccess: (approved) => { qc.invalidateQueries({ queryKey: ['scores', assessmentId] }); toast.success(`${approved.length} score(s) approved.`); },
    onError: () => toast.error('Could not approve scores.'),
  });

  let confirmPublish = $state(false);
  const publishMut = createMutation({
    mutationFn: () => publishAssessment(assessmentId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assessment', assessmentId] }); confirmPublish = false; toast.success('Published. Guardians notified via SMS.'); },
    onError: () => { confirmPublish = false; toast.error('Could not publish.'); },
  });

  // ── Edit ──────────────────────────────────────────────────────────────────────
  let editing  = $state(false);
  let editForm = $state({ name: '', maxScore: '', dueDate: '' });
  let editErr  = $state('');
  function startEdit() {
    const a = $assessmentQ.data!;
    editForm = { name: a.name, maxScore: String(a.max_score), dueDate: a.due_date ?? '' };
    editErr = ''; editing = true;
  }
  const editMut = createMutation({
    mutationFn: () => updateAssessment(assessmentId, { name: editForm.name.trim() || undefined, max_score: parseFloat(editForm.maxScore) || undefined, due_date: editForm.dueDate || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assessment', assessmentId] }); editing = false; toast.success('Assessment updated.'); },
    onError: (e: unknown) => { editErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.'; },
  });

  // ── Delete ────────────────────────────────────────────────────────────────────
  let confirmDelete = $state(false);
  const deleteMut = createMutation({
    mutationFn: () => deleteAssessment(assessmentId),
    onSuccess: () => { goto('/assessments'); toast.success('Assessment deleted.'); },
    onError: () => toast.error('Could not delete assessment.'),
  });

  $effect(() => setPageTitle($assessmentQ.data?.name ?? 'Assessment'));
</script>

<button onclick={() => goto('/assessments')}
  class="mb-3 flex items-center gap-1 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
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
      <!-- Edit form -->
      <div class="space-y-3">
        <div class="grid gap-3 sm:grid-cols-3">
          <div class="sm:col-span-1"><label class="lx">Name</label><input bind:value={editForm.name} class="inp mt-1" /></div>
          <div><label class="lx">Max score</label><input type="number" min="1" step="0.5" bind:value={editForm.maxScore} class="inp mt-1" /></div>
          <div><label class="lx">Due date</label><input type="date" bind:value={editForm.dueDate} class="inp mt-1" /></div>
        </div>
        {#if editErr}<p class="text-xs text-red-500">{editErr}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:opacity-90 transition" style="background:var(--brand)">
            {$editMut.isPending ? 'Saving…' : 'Save changes'}
          </button>
          <button onclick={() => { editing = false; editErr = ''; }}
            class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      </div>

    {:else}
      <!-- View mode -->
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <!-- Info -->
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-lg font-bold text-[var(--fg)]">{a.name}</h1>
            {#if a.is_published}
              <span class="rounded-full bg-green-50 px-2.5 py-0.5 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Published</span>
            {:else}
              <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">Draft</span>
            {/if}
          </div>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">
            {subjectName(a.subject_id)} · {typeName(a.assessment_type_id)} · Max {a.max_score}
            {#if a.due_date}<span class="text-[var(--fg-subtle)]"> · Due {a.due_date}</span>{/if}
          </p>
        </div>

        <!-- Actions (manager only, unpublished only) -->
        {#if !a.is_published && canManage}
          <div class="flex flex-wrap items-center gap-2 sm:shrink-0">
            <!-- Approve pending -->
            {#if unapprovedCount > 0}
              <button onclick={() => $approveMut.mutate()} disabled={$approveMut.isPending}
                class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-xs font-semibold text-[var(--fg)] transition hover:border-[var(--brand)] hover:text-[var(--brand)] disabled:opacity-50">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                {$approveMut.isPending ? 'Approving…' : `Approve ${unapprovedCount}`}
              </button>
            {:else if ($scoresQ.data ?? []).length > 0}
              <span class="flex items-center gap-1 rounded-xl bg-green-50 px-3 py-1.5 text-xs font-semibold text-green-700 dark:bg-green-950/30 dark:text-green-400">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                All approved
              </span>
            {/if}

            <!-- Publish -->
            {#if !confirmPublish}
              <button onclick={() => confirmPublish = true}
                class="rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
                style="background: var(--brand)">
                Publish
              </button>
            {:else}
              <div class="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-1.5">
                <span class="text-xs text-[var(--fg-muted)]">SMS guardians?</span>
                <button onclick={() => $publishMut.mutate()} disabled={$publishMut.isPending}
                  class="rounded-lg bg-green-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition">
                  {$publishMut.isPending ? '…' : 'Yes, publish'}
                </button>
                <button onclick={() => confirmPublish = false} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
              </div>
            {/if}

            <!-- Edit / Delete (secondary) -->
            <button onclick={startEdit} title="Edit"
              class="rounded-xl border border-[var(--border)] p-1.5 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
              </svg>
            </button>

            {#if !confirmDelete}
              <button onclick={() => confirmDelete = true}
                class="rounded-xl border border-[var(--border)] p-1.5 text-[var(--fg-subtle)] transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-800 dark:hover:bg-red-950/30">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            {:else}
              <div class="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 dark:border-red-800 dark:bg-red-950/30">
                <span class="text-xs font-semibold text-red-600 dark:text-red-400">Delete?</span>
                <button onclick={() => $deleteMut.mutate()} disabled={$deleteMut.isPending}
                  class="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50 transition">
                  {$deleteMut.isPending ? '…' : 'Yes'}
                </button>
                <button onclick={() => confirmDelete = false} class="text-xs text-red-600 hover:text-red-800 transition">Cancel</button>
              </div>
            {/if}
          </div>
        {/if}
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
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import {
    getAssessment, getAssessmentRoster, listScores, submitScores, approveScores,
    publishAssessment, updateAssessment, deleteAssessment,
    listAssessmentTypes, assessmentLabel, type Score,
  } from '$lib/api/assessments';
  import { listSubjects, listAllTerms } from '$lib/api/academic';
  import { userRole } from '$lib/stores/permissions';
  import { auth } from '$lib/stores/auth';
  import { queueWrite } from '$lib/offline/outbox';
  import { refreshOutboxCount } from '$lib/offline/sync';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import ScoreTable from './ScoreTable.svelte';
  import AssessmentActionsBar from './AssessmentActionsBar.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  const qc = useQueryClient();
  const assessmentId   = $derived($page.params.id!);
  const canManage      = $derived($userRole === 'admin' || $userRole === 'approver');
  const canEnterScores = $derived($userRole === 'teacher' || canManage);

  const assessmentQ = createQuery({ queryKey: ['assessment', assessmentId], queryFn: () => getAssessment(assessmentId), staleTime: 60_000 });
  const scoresQ     = createQuery({ queryKey: ['scores', assessmentId],     queryFn: () => listScores(assessmentId),     staleTime: 30_000 });
  const subjectsQ   = createQuery({ queryKey: ['subjects'],         queryFn: listSubjects,          staleTime: 5 * 60_000 });
  const typesQ      = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes,   staleTime: 5 * 60_000 });
  const termsQ      = createQuery({ queryKey: ['all-terms'],        queryFn: listAllTerms,          staleTime: 60_000 });

  // Reconstructs the exact filtered list view this assessment belongs to
  // (class/subject/category/term), not just a bare "/assessments" — so
  // "back" works the same whether the teacher arrived from that filtered
  // list, a deep link, or anywhere else. Falls back to the bare list while
  // the assessment is still loading.
  const backHref = $derived.by(() => {
    const a = $assessmentQ.data;
    if (!a) return '/assessments';
    const params = new URLSearchParams({
      class: a.class_id, subject: a.subject_id,
      category: a.assessment_type_id, term: a.academic_term_id,
    });
    return `/assessments?${params}`;
  });

  const termLocked = $derived(
    ($termsQ.data ?? []).find(t => t.id === $assessmentQ.data?.academic_term_id)?.results_locked ?? false
  );

  const studentsQ = reactiveQuery(() => ({
    queryKey: ['assessment-roster', assessmentId] as const,
    queryFn:  () => getAssessmentRoster(assessmentId),
    enabled:  !!$assessmentQ.data,
    staleTime: 60_000,
  }));

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

  // ── Term-lock override ────────────────────────────────────────────────────────
  let lockOverride      = $state<'submit' | 'approve' | 'edit' | null>(null);
  let lockOverrideError = $state('');

  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }
  function isLocked(e: unknown): boolean {
    return (e as { response?: { status?: number } })?.response?.status === 423;
  }

  // ── Mutations ─────────────────────────────────────────────────────────────────
  const submitMut = createMutation({
    mutationFn: async (overrideReason: string | undefined) => {
      const a = $assessmentQ.data!;
      const entries = ($studentsQ.data ?? [])
        .filter(s => scoreInputs[s.id] != null && scoreInputs[s.id] !== '')
        .map(s => ({ student_id: s.id, raw_score: Number(scoreInputs[s.id]) }));
      const invalid = entries.filter(e => isNaN(e.raw_score) || e.raw_score < 0 || e.raw_score > Number(a.max_score));
      if (invalid.length > 0) throw new Error(`${invalid.length} score(s) out of range 0–${a.max_score}.`);
      try {
        return { saved: await submitScores(assessmentId, entries, overrideReason), entries };
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
      lockOverride = null; lockOverrideError = '';
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
    onError: (e: unknown) => {
      if (isLocked(e)) { lockOverride = 'submit'; lockOverrideError = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error(e instanceof Error ? e.message : (detailOf(e) ?? 'Could not save.'));
    },
  });

  const approveMut = createMutation({
    mutationFn: (overrideReason: string | undefined) =>
      approveScores(assessmentId, ($scoresQ.data ?? []).filter(s => !s.is_approved).map(s => s.id), overrideReason),
    onSuccess: (approved) => {
      lockOverride = null; lockOverrideError = '';
      qc.invalidateQueries({ queryKey: ['scores', assessmentId] });
      toast.success(`${approved.length} score(s) approved.`);
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { lockOverride = 'approve'; lockOverrideError = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error('Could not approve scores.');
    },
  });

  let confirmPublish = $state(false);
  const publishMut = createMutation({
    mutationFn: () => publishAssessment(assessmentId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assessment', assessmentId] }); confirmPublish = false; toast.success('Published. Guardians notified via SMS.'); },
    onError: () => { confirmPublish = false; toast.error('Could not publish.'); },
  });

  // ── Edit ──────────────────────────────────────────────────────────────────────
  let editing  = $state(false);
  let editForm = $state({ description: '', maxScore: '', dueDate: '' });
  let editErr  = $state('');
  function startEdit() {
    const a = $assessmentQ.data!;
    editForm = { description: a.description ?? '', maxScore: String(a.max_score), dueDate: a.due_date ?? '' };
    editErr = ''; editing = true;
    // AssessmentActionsBar unmounts while editing — clear any armed confirm
    // prompt so it doesn't silently reappear when editing is cancelled.
    confirmDelete = false; confirmPublish = false;
  }
  const editMut = createMutation({
    mutationFn: (overrideReason: string | undefined) => updateAssessment(assessmentId, {
      description: editForm.description.trim() || undefined,
      max_score: parseFloat(editForm.maxScore) || undefined,
      due_date: editForm.dueDate || null,
    }, overrideReason),
    onSuccess: () => {
      lockOverride = null; lockOverrideError = '';
      qc.invalidateQueries({ queryKey: ['assessment', assessmentId] });
      qc.invalidateQueries({ queryKey: ['assessments'] });
      editing = false; toast.success('Assessment updated.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { lockOverride = 'edit'; lockOverrideError = detailOf(e) ?? 'This term is locked.'; return; }
      editErr = detailOf(e) ?? 'Could not update.';
    },
  });

  // ── Delete ────────────────────────────────────────────────────────────────────
  let confirmDelete = $state(false);
  const deleteMut = createMutation({
    mutationFn: () => deleteAssessment(assessmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessments'] });
      goto(backHref); toast.success('Assessment deleted.');
    },
    onError: (e: unknown) => {
      confirmDelete = false;
      if (isLocked(e)) {
        toast.error(detailOf(e) ?? "This term's results are locked — unlock the term first to delete this assessment.");
        return;
      }
      toast.error('Could not delete assessment.');
    },
  });

  $effect(() => {
    const a = $assessmentQ.data;
    setPageTitle(a ? assessmentLabel(a, typeName(a.assessment_type_id)) : 'Assessment');
  });
</script>

<button onclick={() => goto(backHref)}
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
          <div class="sm:col-span-1"><label class="lx">Description</label><input bind:value={editForm.description} class="inp mt-1" /></div>
          <div><label class="lx">Max score</label><input type="number" min="1" step="0.5" bind:value={editForm.maxScore} class="inp mt-1" /></div>
          <div><label class="lx">Date given to students</label><input type="date" bind:value={editForm.dueDate} class="inp mt-1" /></div>
        </div>
        {#if editErr}<p class="text-xs text-red-500">{editErr}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $editMut.mutate(undefined)} disabled={$editMut.isPending}
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
            <h1 class="text-lg font-bold text-[var(--fg)]">{assessmentLabel(a, typeName(a.assessment_type_id))}</h1>
            {#if a.is_published}
              <span class="rounded-full bg-green-50 px-2.5 py-0.5 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Published</span>
            {:else}
              <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">Draft</span>
            {/if}
            {#if termLocked}
              <span class="rounded-full bg-red-50 px-2.5 py-0.5 text-[10px] font-bold text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-950/30 dark:text-red-400">
                Term locked
              </span>
            {/if}
          </div>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">
            {subjectName(a.subject_id)} · Max {a.max_score}
            {#if a.due_date}<span class="text-[var(--fg-subtle)]"> · Given {a.due_date}</span>{/if}
            {#if a.description}<span class="text-[var(--fg-subtle)]"> · {a.description}</span>{/if}
          </p>
        </div>

        <!-- Actions (unpublished only). Edit/Delete are the owning subject
             teacher's own job (get_assessment is already scope-checked
             server-side, so canEnterScores here is safe — a 'teacher' role
             only ever sees data for a class+subject they teach). Approve/
             Publish stay canManage-only inside the bar. -->
        {#if !a.is_published && canEnterScores}
          <AssessmentActionsBar
            {unapprovedCount}
            hasScores={($scoresQ.data ?? []).length > 0}
            approvePending={$approveMut.isPending}
            onApprove={() => $approveMut.mutate(undefined)}
            bind:confirmPublish
            publishPending={$publishMut.isPending}
            onPublish={() => $publishMut.mutate()}
            onEdit={startEdit}
            bind:confirmDelete
            deletePending={$deleteMut.isPending}
            onDelete={() => $deleteMut.mutate()}
            canApprovePublish={canManage}
          />
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
      onSave={() => $submitMut.mutate(undefined)}
    />
  {/if}
{/if}

<OverrideReasonModal
  open={lockOverride !== null}
  errorMessage={lockOverrideError}
  isPending={lockOverride === 'submit' ? $submitMut.isPending : lockOverride === 'approve' ? $approveMut.isPending : $editMut.isPending}
  onSubmit={(reason) => {
    if (lockOverride === 'submit') $submitMut.mutate(reason);
    else if (lockOverride === 'approve') $approveMut.mutate(reason);
    else if (lockOverride === 'edit') $editMut.mutate(reason);
  }}
  onCancel={() => { lockOverride = null; lockOverrideError = ''; }}
/>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

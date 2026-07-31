<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { getCurrentYear } from '$lib/api/academic';
  import { getSubjectRoster, setSubjectRoster, type SubjectRosterStudent } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { classId: string; subjectId: string; }
  const { classId, subjectId }: Props = $props();

  const qc = useQueryClient();

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const termId = $derived(($yearQ.data?.terms ?? []).find(t => t.is_current)?.id ?? '');

  // Writable store pattern — avoids TanStack's queryKey validation on mount
  // while keeping queryFn reactive to termId, mirroring SubjectsTab.svelte's
  // own subjTeachersOpts.
  const rosterOpts = writable({
    queryKey: ['subject-roster', classId, subjectId, ''] as string[],
    queryFn: () => getSubjectRoster(classId, subjectId, ''),
    enabled: false,
    staleTime: 30_000,
  });
  $effect(() => {
    const t = termId;
    rosterOpts.set({
      queryKey: ['subject-roster', classId, subjectId, t],
      queryFn: () => getSubjectRoster(classId, subjectId, t),
      enabled: !!t,
      staleTime: 30_000,
    });
  });
  const rosterQ = createQuery(rosterOpts);

  let checkedIds = $state<Set<string>>(new Set());
  let initialized = false;
  $effect(() => {
    if (!initialized && $rosterQ.data) {
      checkedIds = new Set($rosterQ.data.filter(s => s.is_registered).map(s => s.student_id));
      initialized = true;
    }
  });

  const enrolledStudents = $derived(($rosterQ.data ?? []).filter(s => s.enrolled));
  const allSelected  = $derived(enrolledStudents.length > 0 && enrolledStudents.every(s => checkedIds.has(s.student_id)));
  const someSelected = $derived(checkedIds.size > 0 && checkedIds.size < enrolledStudents.length);

  function toggleOne(id: string) {
    const next = new Set(checkedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    checkedIds = next;
  }

  function toggleAll() {
    checkedIds = allSelected ? new Set() : new Set(enrolledStudents.map(s => s.student_id));
  }

  // Removing a registration never deletes existing scores, but it does
  // silently block future score edits for that student/subject — warn
  // before a save that would unregister someone who already has scores.
  const studentsLosingScoredAccess = $derived(
    ($rosterQ.data ?? []).filter(s => s.has_scores && s.is_registered && !checkedIds.has(s.student_id))
  );
  let confirmScoreWarning = $state(false);

  function handleSaveClick() {
    if (studentsLosingScoredAccess.length > 0) { confirmScoreWarning = true; return; }
    $saveMut.mutate(undefined);
  }

  let overrideNeeded = $state(false);
  let errorMessage    = $state('');

  function isLocked(e: unknown): boolean {
    return (e as { response?: { status?: number } })?.response?.status === 423;
  }
  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }

  const saveMut = createMutation({
    mutationFn: (overrideReason: string | undefined) =>
      setSubjectRoster(classId, subjectId, termId, [...checkedIds], overrideReason),
    onSuccess: (result) => {
      overrideNeeded = false;
      errorMessage = '';
      qc.invalidateQueries({ queryKey: ['subject-roster', classId, subjectId, termId] });
      const parts: string[] = [];
      if (result.registered > 0) parts.push(`${result.registered} registered`);
      if (result.removed > 0) parts.push(`${result.removed} removed`);
      if (result.skipped > 0) parts.push(`${result.skipped} skipped (not enrolled this term)`);
      toast.success((parts.length ? parts.join(', ') : 'No changes') + '.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { overrideNeeded = true; errorMessage = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error(detailOf(e) ?? 'Failed to save roster.');
    },
  });
</script>

<div class="border-t border-[var(--border)] bg-[var(--hover)]/40 px-4 py-3 space-y-2.5">
  {#if !termId}
    <p class="text-xs text-[var(--fg-muted)]">No current academic term.</p>
  {:else if $rosterQ.isPending}
    <div class="space-y-1.5">{#each [1, 2, 3] as _}<div class="h-6 animate-pulse rounded-lg bg-[var(--hover)]"></div>{/each}</div>
  {:else if ($rosterQ.data ?? []).length === 0}
    <p class="text-xs text-[var(--fg-muted)]">No students actively assigned to this class.</p>
  {:else}
    <label class="flex items-center gap-2 text-xs font-semibold text-[var(--fg)]">
      <input type="checkbox" checked={allSelected} indeterminate={someSelected} onchange={toggleAll}
        class="h-3.5 w-3.5 rounded accent-[var(--brand)]" />
      {allSelected ? 'Deselect all' : `Select all (${enrolledStudents.length})`}
    </label>
    <div class="max-h-64 space-y-1 overflow-y-auto">
      {#each $rosterQ.data ?? [] as s (s.student_id)}
        <label class="flex items-center gap-2 py-0.5 text-sm {s.enrolled ? 'text-[var(--fg)]' : 'text-[var(--fg-subtle)]'}">
          <input type="checkbox" checked={checkedIds.has(s.student_id)} disabled={!s.enrolled}
            onchange={() => toggleOne(s.student_id)}
            class="h-3.5 w-3.5 rounded accent-[var(--brand)] disabled:opacity-40" />
          <span class="flex-1 truncate">{s.display_name}</span>
          {#if s.has_scores}
            <span class="text-amber-500" title="Has scores recorded for this subject — unregistering won't delete them, but will block future score edits until re-registered">⚠</span>
          {/if}
          <span class="font-mono text-[10px] text-[var(--fg-subtle)]">{s.admission_number}</span>
          {#if !s.enrolled}<span class="text-[10px] italic">not enrolled this term</span>{/if}
        </label>
      {/each}
    </div>
    <p class="text-[11px] text-[var(--fg-subtle)]">
      Registering a student for just this subject can affect their automatic eligibility for the class's
      other subjects — for a subject everyone takes, "Register non-elective subjects" above may be simpler.
    </p>
    {#if errorMessage && !overrideNeeded}<p class="text-xs text-red-500">{errorMessage}</p>{/if}
    <button onclick={handleSaveClick} disabled={$saveMut.isPending}
      class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background:var(--brand)">{$saveMut.isPending ? 'Saving…' : 'Save'}</button>
  {/if}
</div>

<ConfirmModal
  open={confirmScoreWarning}
  title="Unregister students with existing scores?"
  message={`${studentsLosingScoredAccess.length} student${studentsLosingScoredAccess.length !== 1 ? 's' : ''} already ${studentsLosingScoredAccess.length !== 1 ? 'have' : 'has'} scores recorded for this subject (${studentsLosingScoredAccess.map(s => s.display_name).join(', ')}). Their existing scores won't be deleted, but this subject can't be re-scored for them until they're re-registered.`}
  confirmLabel="Unregister anyway"
  variant="warning"
  isPending={$saveMut.isPending}
  onConfirm={() => { confirmScoreWarning = false; $saveMut.mutate(undefined); }}
  onCancel={() => confirmScoreWarning = false}
/>

<OverrideReasonModal
  open={overrideNeeded}
  errorMessage={errorMessage}
  isPending={$saveMut.isPending}
  message="This term's results are locked. Changing subject registration this late requires a reason — it is written to the audit log."
  onSubmit={(reason) => $saveMut.mutate(reason)}
  onCancel={() => overrideNeeded = false}
/>

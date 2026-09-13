<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listClassSubjects, listSubjects, listYears, listSubjectTeachers } from '$lib/api/academic';
  import { listPeriods, type SchoolPeriod } from '$lib/api/schoolPeriods';
  import { listStaff } from '$lib/api/staff';
  import { getClassTimetable, upsertTimetableSlot, deleteTimetableSlot, type TimetableSlot } from '$lib/api/timetable';
  import { findCurrentYear } from '$lib/academicPeriod';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import TimetableGrid from './TimetableGrid.svelte';
  import TimetableSlotEditor from './TimetableSlotEditor.svelte';

  interface Props { classId: string; classActive: boolean; }
  const { classId, classActive }: Props = $props();

  const qc = useQueryClient();

  const yearsQ   = createQuery({ queryKey: ['academic-years'],          queryFn: listYears,                        staleTime: 5 * 60_000 });
  const periodsQ = createQuery({ queryKey: ['school-periods'],          queryFn: listPeriods,                      staleTime: 60_000 });
  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],                queryFn: listSubjects,                     staleTime: 5 * 60_000 });
  const staffQ   = createQuery({ queryKey: ['staff'],                   queryFn: () => listStaff({ limit: 200, active_only: true }), staleTime: 5 * 60_000 });

  let yearId = $state('');
  $effect(() => {
    if (yearId) return;
    const cur = findCurrentYear($yearsQ.data ?? []);
    if (cur) yearId = cur.id;
  });

  const timetableQ = reactiveQuery<TimetableSlot[]>(() => ({
    queryKey: ['class-timetable', classId, yearId] as const,
    queryFn:  () => getClassTimetable(classId, yearId),
    enabled:  !!yearId,
    staleTime: 30_000,
  }));

  const subjTeachersQ = reactiveQuery(() => ({
    queryKey: ['subject-teachers', classId, yearId] as const,
    queryFn:  () => listSubjectTeachers(classId, yearId),
    enabled:  !!yearId,
    staleTime: 60_000,
  }));

  const subjectMap             = $derived(new Map(($allSubjQ.data ?? []).map(s => [s.id, s])));
  const classSubjects          = $derived($clsSubjQ.data ?? []);
  const teachingStaff          = $derived(($staffQ.data ?? []).filter(s => s.staff_type === 'TEACHING'));
  const subjectTeacherBySubject = $derived(
    new Map(($subjTeachersQ.data ?? []).map(st => [st.subject_id, st.staff_member_id]))
  );

  function invalidateAfterAssignment() {
    qc.invalidateQueries({ queryKey: ['class-timetable', classId, yearId] });
    qc.invalidateQueries({ queryKey: ['subject-teachers', classId, yearId] });
    // A slot save can auto-add a subject to this class's curriculum (see
    // upsert_timetable_slot's docstring) — refresh so the Subjects tab and
    // this tab's own "already on curriculum" dropdown grouping pick it up.
    qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
  }

  // ── Slot editor ──────────────────────────────────────────────────────────
  let editingPeriod   = $state<SchoolPeriod | null>(null);
  let upsertError     = $state('');
  let upsertErrorCode = $state<string | null>(null);

  function statusOf(e: unknown): number | undefined {
    return (e as { response?: { status?: number } })?.response?.status;
  }
  function errorCodeOf(e: unknown): string | undefined {
    return (e as { response?: { headers?: Record<string, string> } })?.response?.headers?.['x-error-code'];
  }

  function openEditor(period: SchoolPeriod) {
    editingPeriod = period;
    upsertError = '';
    upsertErrorCode = null;
  }

  const currentSlot = $derived(
    editingPeriod ? ($timetableQ.data ?? []).find(s => s.period_id === editingPeriod!.id) : undefined
  );

  const upsertMut = createMutation({
    mutationFn: (args: { subjectId: string; staffMemberId: string }) =>
      upsertTimetableSlot(classId, editingPeriod!.id, yearId, args.subjectId, args.staffMemberId),
    onSuccess: () => {
      invalidateAfterAssignment();
      editingPeriod = null;
      toast.success('Timetable updated.');
    },
    onError: (e) => {
      upsertError = apiError(e, 'Could not save this slot.');
      upsertErrorCode = statusOf(e) === 422 ? (errorCodeOf(e) ?? null) : null;
    },
  });

  // ── Extend into the next period (a double period) ───────────────────────
  // No staff_member_id sent: the subject already has an active SubjectTeacher
  // (that's how the source cell got a teacher shown in the first place), so
  // the backend's omitted-teacher path resolves it automatically — same
  // teacher, no extra round trip to look it up here.
  const extendMut = createMutation({
    mutationFn: (args: { periodId: string; subjectId: string }) =>
      upsertTimetableSlot(classId, args.periodId, yearId, args.subjectId),
    onSuccess: () => { invalidateAfterAssignment(); toast.success('Extended into the next period.'); },
    onError: (e) => toast.error(apiError(e, 'Could not extend into the next period.')),
  });

  // ── Clear slot ───────────────────────────────────────────────────────────
  let confirmClearPeriodId = $state<string | null>(null);
  const clearMut = createMutation({
    mutationFn: (periodId: string) => deleteTimetableSlot(classId, periodId, yearId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-timetable', classId, yearId] });
      editingPeriod = null;
      toast.success('Slot cleared.');
    },
    onError: (e) => toast.error(apiError(e, 'Could not clear slot.')),
  });
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <p class="text-xs text-[var(--fg-muted)]">Click a period to assign its subject and teacher — transcribe a printed FET/aSc timetable slot by slot.</p>
    <div class="relative shrink-0">
      <select bind:value={yearId} class="rounded-xl border border-[var(--border)] bg-[var(--bg)] py-1.5 pl-2.5 pr-7 text-xs text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition appearance-none">
        <option value="">No year</option>
        {#each $yearsQ.data ?? [] as y (y.id)}
          <option value={y.id}>{y.name}{y.is_current ? ' ✓' : ''}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if !yearId}
    <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-10 text-center text-sm text-[var(--fg-muted)]">
      Choose an academic year to manage this class's timetable.
    </div>
  {:else if $periodsQ.isPending || $timetableQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
  {:else}
    <TimetableGrid
      periods={$periodsQ.data ?? []}
      slots={$timetableQ.data ?? []}
      {classActive}
      onCellClick={openEditor}
      onExtend={(period, subjectId) => $extendMut.mutate({ periodId: period.id, subjectId })}
    />
  {/if}
</div>

<TimetableSlotEditor
  open={!!editingPeriod}
  period={editingPeriod}
  {classSubjects}
  allSubjects={($allSubjQ.data ?? []).filter(s => s.is_active)}
  {subjectMap}
  {teachingStaff}
  {currentSlot}
  {subjectTeacherBySubject}
  isPending={$upsertMut.isPending}
  errorMessage={upsertError}
  errorCode={upsertErrorCode}
  onSave={(args) => $upsertMut.mutate(args)}
  onClear={() => { confirmClearPeriodId = editingPeriod?.id ?? null; }}
  onCancel={() => { editingPeriod = null; }}
/>

<ConfirmModal
  open={!!confirmClearPeriodId}
  title="Clear this slot?"
  message="This period will no longer have a subject assigned for this class."
  confirmLabel="Clear"
  isPending={$clearMut.isPending}
  onConfirm={() => { $clearMut.mutate(confirmClearPeriodId!); confirmClearPeriodId = null; }}
  onCancel={() => confirmClearPeriodId = null}
/>

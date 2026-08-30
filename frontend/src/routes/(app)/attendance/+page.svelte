<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listYears } from '$lib/api/academic';
  import { findCurrentTerm } from '$lib/academicPeriod';
  import { listStudents } from '$lib/api/students';
  import {
    listCalendar, listAttendanceRecords, markAttendance, getClassSummaries, listMyAttendanceClasses,
    type AttendanceStatus, type CalendarDay, type StudentAbsenceSummary,
  } from '$lib/api/attendance';
  import { getMySchool } from '$lib/api/schools';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import { userRole } from '$lib/stores/permissions';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';
  import AttendanceSelectors from './AttendanceSelectors.svelte';
  import AttendanceMarkingOverview from './AttendanceMarkingOverview.svelte';
  import AttendancePeriodMarkingOverview from './AttendancePeriodMarkingOverview.svelte';
  import AttendancePeriodPicker from './AttendancePeriodPicker.svelte';
  import AttendanceRosterPanel from './AttendanceRosterPanel.svelte';
  import { queueAttendanceOffline } from './offlineQueue';
  setPageTitle('Attendance');

  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }
  function isLocked(e: unknown): boolean {
    return (e as { response?: { status?: number } })?.response?.status === 423;
  }

  const qc = useQueryClient();
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Selectors ─────────────────────────────────────────────────────────────────
  const today = new Date().toISOString().slice(0, 10);
  let classId      = $state('');
  let selectedDate = $state(today);
  let periodId     = $state<string | null>(null);

  const schoolQ = createQuery({ queryKey: ['my-school'], queryFn: getMySchool, staleTime: 60_000 });
  const periodAttendanceOn = $derived($schoolQ.data?.has_period_attendance ?? false);
  // A period picked for a different class/day would be stale — every path
  // that changes classId/selectedDate on its own resets periodId to null
  // explicitly (not a reactive $effect keyed on classId, since
  // AttendancePeriodMarkingOverview's onSelect below intentionally sets
  // both classId and periodId together — an effect would immediately
  // clobber that back to null).

  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });

  const allTerms      = $derived(($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name }))));
  const currentTermId = $derived(findCurrentTerm(allTerms)?.id ?? '');

  // Scoped to the caller's own ClassTeacher assignment(s) unless they hold
  // attendance.approve — the backend decides, this page just renders whatever
  // it gets back, same for every role.
  const classesQ = reactiveQuery(() => ({
    queryKey: ['my-attendance-classes', currentTermId] as const,
    queryFn:  () => listMyAttendanceClasses(currentTermId),
    enabled:  !!currentTermId,
    staleTime: 5 * 60_000,
  }));

  const classes = $derived($classesQ.data ?? []);

  // Auto-select when there's only one class — same courtesy as the class/
  // subject/category auto-selects on /assessments (assessments/+page.svelte).
  $effect(() => {
    if (classes.length === 1 && !classId) classId = classes[0].id;
  });

  // ── Calendar for current term ──────────────────────────────────────────────────
  const calendarQ = reactiveQuery(() => ({
    queryKey: ['calendar', currentTermId] as const,
    queryFn:  () => listCalendar(currentTermId),
    enabled:  !!currentTermId,
    staleTime: 10 * 60_000,
  }));

  const calByDate  = $derived(new Map<string, CalendarDay>(($calendarQ.data ?? []).map(d => [d.date, d])));
  const calDay     = $derived(calByDate.get(selectedDate) ?? null);
  const MARKABLE   = new Set(['SCHOOL_DAY', 'EXAM_DAY', 'HALF_DAY']);
  const isMarkable = $derived(!!calDay && MARKABLE.has(calDay.day_type));

  // ── Students for selected class ────────────────────────────────────────────────
  // Two queries: every class-assigned student (so an unregistered-but-
  // present student is still visible, not hidden), and the subset actually
  // registered ("physically reported") for the current term — only the
  // latter can be marked. A class teacher can self-serve register the rest
  // right here via NotRegisteredBanner below, instead of being sent to the
  // class detail page's Students tab.
  const classStudentsQ = reactiveQuery(() => ({
    queryKey: ['students-for-class', classId] as const,
    queryFn:  () => listStudents({ class_id: classId }),
    enabled:  !!classId,
    staleTime: 60_000,
  }));
  const termRegisteredQ = reactiveQuery(() => ({
    queryKey: ['students-for-class', classId, currentTermId] as const,
    queryFn:  () => listStudents({ class_id: classId, term_id: currentTermId }),
    enabled:  !!classId && !!currentTermId,
    staleTime: 60_000,
  }));
  const registeredIds      = $derived(new Set(($termRegisteredQ.data ?? []).map(s => s.id)));
  const classStudents      = $derived($classStudentsQ.data ?? []);
  const registeredStudents = $derived(classStudents.filter(s => registeredIds.has(s.id)));
  const notRegistered      = $derived(classStudents.filter(s => !registeredIds.has(s.id)));

  // ── Existing records for this day + class (+ period, when picked) ───────────────
  const recordsQ = reactiveQuery(() => ({
    queryKey: ['att-records', calDay?.id ?? '', classId, periodId] as const,
    queryFn:  () => listAttendanceRecords(calDay!.id, classId, periodId),
    enabled:  !!classId && !!calDay,
    staleTime: 30_000,
  }));

  // ── Class absence summaries (for inline per-student display) ───────────────────
  const classSummariesQ = reactiveQuery(() => ({
    queryKey: ['att-summaries', classId, currentTermId] as const,
    queryFn:  () => getClassSummaries(classId, currentTermId),
    enabled:  !!classId && !!currentTermId,
    staleTime: 5 * 60_000,
  }));

  // ── Derived counts ─────────────────────────────────────────────────────────────
  const summaryMap   = $derived(new Map<string, StudentAbsenceSummary>(($classSummariesQ.data ?? []).map(s => [s.student_id, s])));
  const recordCount  = $derived($recordsQ.data?.length ?? 0);
  const studentCount = $derived(registeredStudents.length);

  // ── Status inputs ─────────────────────────────────────────────────────────────
  // Exception-based: every student defaults to Present the moment the roster
  // loads, so the teacher only ever taps the few who are Absent/Late/Excused —
  // no separate "mark all present" step, no unmarked-students warning, no
  // extra tap for the common case (most students present most days).
  let markInputs     = $state<Record<string, AttendanceStatus | ''>>({});
  let initializedFor = $state<string | null>(null);

  $effect(() => {
    const key = `${classId}-${calDay?.id ?? ''}-${periodId ?? ''}`;
    if ($recordsQ.data !== undefined && $termRegisteredQ.data !== undefined && initializedFor !== key) {
      const init: Record<string, AttendanceStatus | ''> = {};
      for (const r of $recordsQ.data) init[r.student_id] = r.status;
      for (const s of registeredStudents) if (!(s.id in init)) init[s.id] = 'PRESENT';
      markInputs = init; initializedFor = key;
    }
  });

  function handleSave() {
    $markMut.mutate(undefined);
  }

  // ── Mutation ──────────────────────────────────────────────────────────────────
  let markOverrideNeeded = $state(false);
  let markError = $state('');

  const markMut = createMutation({
    mutationFn: async (overrideReason: string | undefined) => {
      // A toggled-off status (tapping an already-active button clears it back
      // to '') still counts as Present — blank means "no exception," not
      // "unrecorded," under the exception-based model above.
      const records = registeredStudents
        .map(s => ({ student_id: s.id, status: (markInputs[s.id] || 'PRESENT') as AttendanceStatus }));
      try {
        const saved = await markAttendance({
          school_calendar_id: calDay!.id, class_id: classId, records, override_reason: overrideReason,
          period_id: periodId,
        });
        return { saved, records };
      } catch (err: unknown) {
        // No response → network unreachable; queue for later sync — same
        // fallback the Assessments score-entry page uses. periodId flows
        // through unchanged (undefined/null queues the whole-day mark).
        if (!(err as { response?: unknown }).response) {
          await queueAttendanceOffline(calDay!.id, classId, records, periodId);
          return { saved: null, records };
        }
        throw err;
      }
    },
    onSuccess: ({ saved, records }) => {
      markOverrideNeeded = false; markError = '';
      if (!saved) {
        toast.info('No connection — attendance queued and will sync when you reconnect.');
        return;
      }
      qc.invalidateQueries({ queryKey: ['att-records'] });
      qc.invalidateQueries({ queryKey: ['att-summaries'] });
      qc.invalidateQueries({ queryKey: ['markable-periods'] });
      toast.success(`${saved.length} record(s) saved.`);
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { markOverrideNeeded = true; markError = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error(e instanceof Error ? e.message : (detailOf(e) ?? 'Could not save.'));
    },
  });

  // ── Status helpers ─────────────────────────────────────────────────────────────
  const dayTypeColor: Record<string, string> = {
    SCHOOL_DAY: 'bg-green-100 text-green-700', EXAM_DAY: 'bg-purple-100 text-purple-700',
    HALF_DAY: 'bg-blue-100 text-blue-700', PUBLIC_HOLIDAY: 'bg-red-100 text-red-700',
    SCHOOL_HOLIDAY: 'bg-amber-100 text-amber-700', WEEKEND: 'bg-gray-100 text-gray-600',
  };
</script>

{#if !currentTermId}
  <EmptyState compact title="No current academic term"
    description="Set a term as current in Academic setup before marking attendance."
    {...(canManage ? { action: () => goto('/admin/academic'), actionLabel: 'Go to setup' } : {})} />
{:else}
<AttendanceSelectors
  {classId} {classes} {today} {selectedDate} {calDay} {dayTypeColor}
  onClassChange={(id) => { classId = id; periodId = null; }}
  onDateChange={(date) => { selectedDate = date; periodId = null; }}
/>

{#if $calendarQ.isPending}
  <div class="h-24 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else if !calDay}
  <div class="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)] p-8 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No calendar entry for <strong>{selectedDate}</strong>.</p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Ensure the calendar has been generated for this term under the Calendar tab.</p>
  </div>
{:else if !isMarkable}
  <div class="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-center dark:border-amber-900 dark:bg-amber-950/30">
    <p class="text-sm font-medium text-amber-700 dark:text-amber-400">
      Cannot mark attendance — this date is classified as <strong>{calDay.day_type.replace(/_/g, ' ')}</strong>.
    </p>
    {#if canManage}
      <p class="mt-1 text-xs text-amber-600 dark:text-amber-500">
        If this is wrong, go to the <a href="/attendance/calendar" class="underline font-semibold">Calendar tab</a> to override this day, or use "Regenerate" to re-evaluate the whole term against the current schedule.
      </p>
    {:else}
      <p class="mt-1 text-xs text-amber-600 dark:text-amber-500">Contact your administrator to correct this calendar entry.</p>
    {/if}
  </div>
{:else if !classId && classes.length > 1}
  <!-- The "who's marked, who hasn't" overview — an admin (or any caller with
       more than one class in scope) lands here instead of a bare class
       picker, so they can see who to chase up or mark on behalf of. -->
  <AttendanceMarkingOverview calendarId={calDay.id} onSelectClass={(id) => { classId = id; periodId = null; }} />
  <AttendancePeriodMarkingOverview
    calendarId={calDay.id} enabled={periodAttendanceOn}
    onSelect={(cid, pid) => { classId = cid; periodId = pid; }}
  />
{:else if !classId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
    Select a class to mark attendance.
  </div>
{:else}
  <AttendancePeriodPicker
    {classId} calendarId={calDay.id} enabled={periodAttendanceOn} {periodId}
    onSelect={(id) => periodId = id}
  />

  <AttendanceRosterPanel
    {recordCount} {studentCount}
    classStudentsLoading={$classStudentsQ.isPending || $termRegisteredQ.isPending}
    {classStudents} {notRegistered} {registeredIds} {currentTermId}
    termName={allTerms.find(t => t.id === currentTermId)?.name ?? 'this term'}
    {markInputs} {summaryMap}
    isSaving={$markMut.isPending}
    onSave={handleSave}
    onToggle={(studentId, value) => markInputs[studentId] = value}
    onRegistered={() => qc.invalidateQueries({ queryKey: ['students-for-class', classId] })}
  />
{/if}
{/if}

<OverrideReasonModal
  open={markOverrideNeeded}
  errorMessage={markError}
  isPending={$markMut.isPending}
  onSubmit={(reason) => $markMut.mutate(reason)}
  onCancel={() => { markOverrideNeeded = false; markError = ''; }}
/>

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
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import { userRole } from '$lib/stores/permissions';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';
  import NotRegisteredBanner from '$lib/components/NotRegisteredBanner.svelte';
  import AttendanceSelectors from './AttendanceSelectors.svelte';
  import AttendanceStudentRow from './AttendanceStudentRow.svelte';
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

  // Auto-select when there's only one class — same courtesy as the class/
  // subject/category auto-selects on /assessments (assessments/+page.svelte).
  $effect(() => {
    const classes = $classesQ.data ?? [];
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

  // ── Existing records for this day + class ──────────────────────────────────────
  const recordsQ = reactiveQuery(() => ({
    queryKey: ['att-records', calDay?.id ?? '', classId] as const,
    queryFn:  () => listAttendanceRecords(calDay!.id, classId),
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
    const key = `${classId}-${calDay?.id ?? ''}`;
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
    mutationFn: (overrideReason: string | undefined) => {
      // A toggled-off status (tapping an already-active button clears it back
      // to '') still counts as Present — blank means "no exception," not
      // "unrecorded," under the exception-based model above.
      const records = registeredStudents
        .map(s => ({ student_id: s.id, status: (markInputs[s.id] || 'PRESENT') as string }));
      return markAttendance({ school_calendar_id: calDay!.id, class_id: classId, records, override_reason: overrideReason });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['att-records'] });
      qc.invalidateQueries({ queryKey: ['att-summaries'] });
      markOverrideNeeded = false; markError = '';
      toast.success(`${res.length} record(s) saved.`);
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
  {classId} classes={$classesQ.data ?? []} {today} {selectedDate} {calDay} {dayTypeColor}
  onClassChange={(id) => classId = id}
  onDateChange={(date) => selectedDate = date}
/>

{#if !classId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
    Select a class to mark attendance.
  </div>
{:else if $calendarQ.isPending}
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
{:else}
  <!-- Submission status banner -->
  {#if recordCount > 0 && studentCount > 0}
    {#if recordCount >= studentCount}
      <div class="mb-3 flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-2.5 dark:border-green-900 dark:bg-green-950/30">
        <span class="text-green-600 dark:text-green-400">✓</span>
        <span class="text-sm font-medium text-green-700 dark:text-green-300">Attendance fully submitted — {recordCount} records saved.</span>
      </div>
    {:else}
      <div class="mb-3 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 dark:border-amber-900 dark:bg-amber-950/30">
        <span class="text-amber-600 dark:text-amber-400">⚠</span>
        <span class="text-sm font-medium text-amber-700 dark:text-amber-300">Partially submitted — {recordCount} of {studentCount} students recorded.</span>
      </div>
    {/if}
  {/if}

  <!-- Action bar -->
  <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
    <p class="text-xs text-[var(--fg-muted)]">
      {studentCount} student(s) · everyone starts Present — tap a student to change to Absent, Late, or Excused
    </p>
    <button onclick={handleSave} disabled={$markMut.isPending || studentCount === 0}
      class="min-h-[44px] rounded-xl px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
      {$markMut.isPending ? 'Saving…' : 'Save attendance'}
    </button>
  </div>

  <!-- Student list -->
  {#if $classStudentsQ.isPending || $termRegisteredQ.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if classStudents.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
      No students assigned to this class yet.
    </div>
  {:else}
    {#if notRegistered.length > 0}
      <div class="mb-3">
        <NotRegisteredBanner
          items={notRegistered.map(s => ({ student_id: s.id, academic_term_id: currentTermId }))}
          termName={allTerms.find(t => t.id === currentTermId)?.name ?? 'this term'}
          onRegistered={() => qc.invalidateQueries({ queryKey: ['students-for-class', classId] })}
        />
      </div>
    {/if}
    <!-- Legend — the row buttons are single-letter for space, spelled out once here
         rather than relying on a hover title (doesn't work on touch). -->
    <div class="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-xs text-[var(--fg-muted)]">
      <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-green-500"></span>P = Present</span>
      <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-red-500"></span>A = Absent</span>
      <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-amber-500"></span>L = Late</span>
      <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-blue-500"></span>E = Excused</span>
    </div>
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      {#each classStudents as student, i (student.id)}
        {@const cur = markInputs[student.id] ?? ''}
        <AttendanceStudentRow
          {student} index={i} status={cur} summary={summaryMap.get(student.id)}
          registered={registeredIds.has(student.id)}
          onToggle={(code) => markInputs[student.id] = cur === code ? '' : code}
        />
      {/each}
    </div>
  {/if}
{/if}
{/if}

<OverrideReasonModal
  open={markOverrideNeeded}
  errorMessage={markError}
  isPending={$markMut.isPending}
  onSubmit={(reason) => $markMut.mutate(reason)}
  onCancel={() => { markOverrideNeeded = false; markError = ''; }}
/>

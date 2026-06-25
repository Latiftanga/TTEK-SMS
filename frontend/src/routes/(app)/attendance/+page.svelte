<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listClasses, listYears } from '$lib/api/academic';
  import { listStudents } from '$lib/api/students';
  import {
    listCalendar, listAttendanceRecords, markAttendance, getClassSummaries,
    type AttendanceStatus, type CalendarDay, type StudentAbsenceSummary,
  } from '$lib/api/attendance';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Attendance');

  const qc = useQueryClient();

  // ── Selectors ─────────────────────────────────────────────────────────────────
  const today = new Date().toISOString().slice(0, 10);
  let classId      = $state('');
  let selectedDate = $state(today);

  const classesQ = createQuery({ queryKey: ['classes'],        queryFn: listClasses, staleTime: 5 * 60_000 });
  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });

  const allTerms      = $derived(($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name }))));
  const currentTermId = $derived(allTerms.find(t => t.is_current)?.id ?? '');

  // ── Calendar for current term ──────────────────────────────────────────────────
  const calOpts = writable({ queryKey: ['calendar', ''] as const, queryFn: () => listCalendar(''), enabled: false, staleTime: 10 * 60_000 });
  $effect(() => { if (currentTermId) calOpts.set({ queryKey: ['calendar', currentTermId] as const, queryFn: () => listCalendar(currentTermId), enabled: true, staleTime: 10 * 60_000 }); });
  const calendarQ = createQuery(calOpts);

  const calByDate  = $derived(new Map<string, CalendarDay>(($calendarQ.data ?? []).map(d => [d.date, d])));
  const calDay     = $derived(calByDate.get(selectedDate) ?? null);
  const MARKABLE   = new Set(['SCHOOL_DAY', 'EXAM_DAY', 'HALF_DAY']);
  const isMarkable = $derived(!!calDay && MARKABLE.has(calDay.day_type));

  // ── Students ──────────────────────────────────────────────────────────────────
  const studentsOpts = writable({ queryKey: ['students-for-class', ''] as const, queryFn: () => listStudents({}), enabled: false, staleTime: 60_000 });
  $effect(() => { if (classId) studentsOpts.set({ queryKey: ['students-for-class', classId] as const, queryFn: () => listStudents({ class_id: classId }), enabled: true, staleTime: 60_000 }); });
  const studentsQ = createQuery(studentsOpts);

  // ── Existing records for this day + class ──────────────────────────────────────
  const recOpts = writable({ queryKey: ['att-records', '', ''] as const, queryFn: () => listAttendanceRecords('', ''), enabled: false, staleTime: 30_000 });
  $effect(() => {
    if (classId && calDay) {
      const cid = classId, did = calDay.id;
      recOpts.set({ queryKey: ['att-records', did, cid] as const, queryFn: () => listAttendanceRecords(did, cid), enabled: true, staleTime: 30_000 });
    }
  });
  const recordsQ = createQuery(recOpts);

  // ── Class absence summaries (bulk, for inline display) ─────────────────────────
  const summOpts = writable({ queryKey: ['att-summaries', '', ''] as const, queryFn: () => getClassSummaries('', ''), enabled: false, staleTime: 5 * 60_000 });
  $effect(() => {
    if (classId && currentTermId) summOpts.set({ queryKey: ['att-summaries', classId, currentTermId] as const, queryFn: () => getClassSummaries(classId, currentTermId), enabled: true, staleTime: 5 * 60_000 });
  });
  const classSummariesQ = createQuery(summOpts);

  // ── Derived counts ─────────────────────────────────────────────────────────────
  const summaryMap   = $derived(new Map<string, StudentAbsenceSummary>(($classSummariesQ.data ?? []).map(s => [s.student_id, s])));
  const recordCount  = $derived($recordsQ.data?.length ?? 0);
  const studentCount = $derived($studentsQ.data?.length ?? 0);

  // ── Status inputs ─────────────────────────────────────────────────────────────
  let markInputs     = $state<Record<string, AttendanceStatus | ''>>({});
  let initializedFor = $state<string | null>(null);

  $effect(() => {
    const key = `${classId}-${calDay?.id ?? ''}`;
    if ($recordsQ.data !== undefined && initializedFor !== key) {
      const init: Record<string, AttendanceStatus | ''> = {};
      for (const r of $recordsQ.data) init[r.student_id] = r.status;
      markInputs = init; initializedFor = key;
    }
  });

  const unmarkedCount = $derived(($studentsQ.data ?? []).filter(s => !markInputs[s.id]).length);

  // ── Mark-all-present with guard ────────────────────────────────────────────────
  let confirmMarkAll = $state(false);

  function markAllPresent() {
    const hasNonPresent = ($studentsQ.data ?? []).some(s => markInputs[s.id] && markInputs[s.id] !== 'PRESENT');
    if (hasNonPresent) { confirmMarkAll = true; return; }
    for (const s of $studentsQ.data ?? []) markInputs[s.id] = 'PRESENT';
  }
  function doMarkAllPresent() {
    for (const s of $studentsQ.data ?? []) markInputs[s.id] = 'PRESENT';
    confirmMarkAll = false;
  }
  function markRemainingPresent() {
    for (const s of $studentsQ.data ?? []) if (!markInputs[s.id]) markInputs[s.id] = 'PRESENT';
    showUnmarkedWarning = false;
  }

  // ── Save guard ────────────────────────────────────────────────────────────────
  let showUnmarkedWarning = $state(false);

  function handleSave() {
    if (unmarkedCount > 0) { showUnmarkedWarning = true; return; }
    $markMut.mutate();
  }

  // ── Mutation ──────────────────────────────────────────────────────────────────
  const markMut = createMutation({
    mutationFn: () => {
      const records = ($studentsQ.data ?? [])
        .filter(s => markInputs[s.id])
        .map(s => ({ student_id: s.id, status: markInputs[s.id] as string }));
      if (!records.length) throw new Error('Select a status for at least one student.');
      return markAttendance({ school_calendar_id: calDay!.id, class_id: classId, records });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['att-records'] });
      qc.invalidateQueries({ queryKey: ['att-summaries'] });
      showUnmarkedWarning = false;
      toast.success(`${res.length} record(s) saved.`);
    },
    onError: (e: unknown) => toast.error(
      e instanceof Error ? e.message : ((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save.')
    ),
  });

  // ── Status helpers ─────────────────────────────────────────────────────────────
  type StatusOption = { code: AttendanceStatus; label: string; active: string; idle: string };
  const STATUSES: StatusOption[] = [
    { code: 'PRESENT', label: 'P', active: 'bg-green-500 text-white', idle: 'border border-green-300 text-green-700 hover:bg-green-50 dark:border-green-800 dark:text-green-400 dark:hover:bg-green-950/40' },
    { code: 'ABSENT',  label: 'A', active: 'bg-red-500 text-white',   idle: 'border border-red-300 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40' },
    { code: 'LATE',    label: 'L', active: 'bg-amber-500 text-white', idle: 'border border-amber-300 text-amber-700 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-950/40' },
    { code: 'EXCUSED', label: 'E', active: 'bg-blue-500 text-white',  idle: 'border border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-800 dark:text-blue-400 dark:hover:bg-blue-950/40' },
  ];

  const dayTypeColor: Record<string, string> = {
    SCHOOL_DAY: 'bg-green-100 text-green-700', EXAM_DAY: 'bg-purple-100 text-purple-700',
    HALF_DAY: 'bg-blue-100 text-blue-700', PUBLIC_HOLIDAY: 'bg-red-100 text-red-700',
    SCHOOL_HOLIDAY: 'bg-amber-100 text-amber-700', WEEKEND: 'bg-gray-100 text-gray-600',
  };
</script>

<!-- Selectors -->
<div class="mb-5 flex flex-wrap items-end gap-3">
  <div>
    <label class="label" for="att-class">Class</label>
    <select id="att-class" bind:value={classId} class="sel">
      <option value="">Select class…</option>
      {#each $classesQ.data ?? [] as c (c.id)}
        <option value={c.id}>{c.display_name}</option>
      {/each}
    </select>
  </div>
  <div>
    <label class="label" for="att-date">Date</label>
    <input id="att-date" type="date" bind:value={selectedDate} class="sel" />
  </div>
  {#if calDay}
    <span class="mb-1 rounded-full px-3 py-1 text-xs font-semibold {dayTypeColor[calDay.day_type]}">
      {calDay.day_type.replace('_', ' ')}
      {#if calDay.notes} · {calDay.notes}{/if}
    </span>
  {/if}
</div>

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
      Cannot mark attendance on a {calDay.day_type.replace('_', ' ')} day.
    </p>
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
    <p class="text-xs text-[var(--fg-muted)]">{studentCount} student(s)</p>
    <div class="flex gap-2">
      {#if confirmMarkAll}
        <div class="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-1.5 dark:border-amber-900 dark:bg-amber-950/30">
          <span class="text-xs text-amber-700 dark:text-amber-300">Override existing marks?</span>
          <button onclick={doMarkAllPresent} class="rounded-lg bg-amber-500 px-2.5 py-1 text-xs font-semibold text-white hover:opacity-90 transition">Yes, mark all</button>
          <button onclick={() => confirmMarkAll = false} class="rounded-lg px-2.5 py-1 text-xs font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
        </div>
      {:else}
        <button onclick={markAllPresent} class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Mark all present
        </button>
      {/if}
      <button onclick={handleSave} disabled={$markMut.isPending}
        class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
        {$markMut.isPending ? 'Saving…' : 'Save attendance'}
      </button>
    </div>
  </div>

  <!-- Student list -->
  {#if $studentsQ.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if studentCount === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">No students in this class.</div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      {#each $studentsQ.data ?? [] as student, i (student.id)}
        {@const cur     = markInputs[student.id] ?? ''}
        {@const summary = summaryMap.get(student.id)}
        <div class="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-0 {i % 2 === 1 ? 'bg-[var(--hover)]' : ''}">
          <span class="w-7 text-right text-xs font-mono text-[var(--fg-subtle)]">{i + 1}</span>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-[var(--fg)]">{student.display_name}</p>
            <div class="flex items-center gap-2">
              <p class="text-[10px] font-mono text-[var(--fg-subtle)]">{student.admission_number}</p>
              {#if summary && summary.days_absent > 0}
                <span class="text-[10px] font-semibold text-red-500" title="{summary.days_absent} absences this term">{summary.days_absent} abs</span>
              {/if}
              {#if summary && summary.days_late > 0}
                <span class="text-[10px] font-semibold text-amber-500" title="{summary.days_late} lates this term">{summary.days_late} late</span>
              {/if}
            </div>
          </div>
          <div class="flex gap-1">
            {#each STATUSES as s}
              <button onclick={() => markInputs[student.id] = cur === s.code ? '' : s.code}
                class="h-8 w-8 rounded-lg text-xs font-bold transition {cur === s.code ? s.active : s.idle}"
                title={s.code}>
                {s.label}
              </button>
            {/each}
          </div>
        </div>
      {/each}
    </div>

    <!-- Unmarked students warning -->
    {#if showUnmarkedWarning}
      <div class="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
        <p class="text-sm font-medium text-amber-800 dark:text-amber-200">{unmarkedCount} student(s) have no status selected and won't be saved.</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button onclick={markRemainingPresent} class="rounded-lg bg-green-500 px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 transition">Mark remaining as Present</button>
          <button onclick={() => { showUnmarkedWarning = false; $markMut.mutate(); }} class="rounded-lg px-3 py-1.5 text-xs font-semibold border border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Save anyway</button>
          <button onclick={() => showUnmarkedWarning = false} class="rounded-lg px-3 py-1.5 text-xs text-[var(--fg-subtle)] hover:text-[var(--fg)] transition">Cancel</button>
        </div>
      </div>
    {/if}
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

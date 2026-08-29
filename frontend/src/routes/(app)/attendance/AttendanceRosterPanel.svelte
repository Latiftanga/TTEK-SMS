<script lang="ts">
  import type { StudentSummary } from '$lib/api/students';
  import type { AttendanceStatus, StudentAbsenceSummary } from '$lib/api/attendance';
  import NotRegisteredBanner from '$lib/components/NotRegisteredBanner.svelte';
  import AttendanceStudentRow from './AttendanceStudentRow.svelte';

  interface Props {
    recordCount: number;
    studentCount: number;
    classStudentsLoading: boolean;
    classStudents: StudentSummary[];
    notRegistered: StudentSummary[];
    registeredIds: Set<string>;
    currentTermId: string;
    termName: string;
    markInputs: Record<string, AttendanceStatus | ''>;
    summaryMap: Map<string, StudentAbsenceSummary>;
    isSaving: boolean;
    onSave: () => void;
    onToggle: (studentId: string, value: AttendanceStatus | '') => void;
    onRegistered: () => void;
  }
  const {
    recordCount, studentCount, classStudentsLoading, classStudents, notRegistered,
    registeredIds, currentTermId, termName, markInputs, summaryMap, isSaving,
    onSave, onToggle, onRegistered,
  }: Props = $props();
</script>

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
  <button onclick={onSave} disabled={isSaving || studentCount === 0}
    class="min-h-[44px] rounded-xl px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
    {isSaving ? 'Saving…' : 'Save attendance'}
  </button>
</div>

<!-- Student list -->
{#if classStudentsLoading}
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
        {termName}
        {onRegistered}
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
        onToggle={(code) => onToggle(student.id, cur === code ? '' : code)}
      />
    {/each}
  </div>
{/if}

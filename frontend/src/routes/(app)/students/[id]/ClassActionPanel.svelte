<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listClassAssignments, listGraduationRecords, bulkPromoteStudents, type PromotionRecordCreate,
  } from '$lib/api/students';
  import { type SchoolClass } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';
  import { detailOf, isLocked } from '$lib/apiError';
  import TargetClassPicker from '$lib/components/TargetClassPicker.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';
  import TransferOutPanel from './TransferOutPanel.svelte';

  interface Props {
    studentId: string;
    activeClass: SchoolClass | null;
    classes: SchoolClass[];
    years: import('$lib/api/academic').AcademicYear[];
    onDone: (newAssignmentId: string) => void;
    // Promote/Repeat/Demote/Graduate are admin-tier (Category D,
    // core/student_scope.py) — irreversible, school-wide structural actions,
    // not a class teacher's own-class job. Transfer-out creation stays
    // pastoral (Category A), gated on canEdit like the rest of the tab.
    canEdit?: boolean;
    canManage?: boolean;
  }
  const { studentId, activeClass, classes, years, onDone, canEdit = true, canManage = true }: Props = $props();

  const qc = useQueryClient();

  // Year-end progression already writes a GraduationRecord via the bulk endpoint
  // (services/promotion.py) — fetch this student's own history so the panel can
  // show "already processed" instead of presenting Promote/Repeat/Demote as if
  // nothing has happened yet, and warn before a duplicate submission that the
  // server would just silently skip.
  // GET /students/graduation is admin-tier (students.delete) — only fetch when
  // canManage, so a class-teacher-only caller opening this panel just to use
  // TransferOutPanel doesn't eat an avoidable 403.
  const graduationRecordsQ = createQuery({
    queryKey: ['student-graduation-records', studentId],
    queryFn:  () => listGraduationRecords({ student_id: studentId }),
    enabled: canManage,
    staleTime: 30_000,
  });
  const currentYear = $derived(years.find(y => y.is_current) ?? null);
  const currentYearRecord = $derived(
    currentYear ? ($graduationRecordsQ.data ?? []).find(r => r.academic_year_id === currentYear.id) ?? null : null
  );
  const OUTCOME_LABEL: Record<string, string> = { PROMOTED: 'Promoted', REPEATED: 'Repeated', DEMOTED: 'Demoted' };

  type ActionMode = 'promote' | 'repeat' | 'demote' | null;
  let actionMode     = $state<ActionMode>(null);
  let caYearId       = $state('');
  let caClassId      = $state('');
  let caError        = $state('');
  let alsoEnroll     = $state(true);
  let overrideNeeded = $state(false);
  let overrideError  = $state('');

  const targetYear = $derived(years.find(y => y.id === caYearId) ?? null);
  const firstTerm  = $derived([...(targetYear?.terms ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date))[0] ?? null);
  const targetYearRecord = $derived(
    caYearId ? ($graduationRecordsQ.data ?? []).find(r => r.academic_year_id === caYearId) ?? null : null
  );

  function openAction(mode: ActionMode) {
    actionMode = mode; caYearId = ''; caClassId = ''; caError = ''; alsoEnroll = true;
  }

  const ACTION_TO_TYPE: Record<'promote' | 'repeat' | 'demote', PromotionRecordCreate['graduation_type']> = {
    promote: 'PROMOTED', repeat: 'REPEATED', demote: 'DEMOTED',
  };

  const assignMut = createMutation({
    mutationFn: (overrideReason?: string) => bulkPromoteStudents({
      academic_year_id: caYearId,
      academic_term_id: alsoEnroll && firstTerm ? firstTerm.id : null,
      records: [{ student_id: studentId, class_id: caClassId, graduation_type: ACTION_TO_TYPE[actionMode ?? 'promote'] }],
      override_reason: overrideReason,
    }),
    onSuccess: async (res) => {
      qc.invalidateQueries({ queryKey: ['student-term-enrollments', studentId] });
      qc.invalidateQueries({ queryKey: ['student-graduation-records', studentId] });
      const labels: Record<string, string> = { promote: 'Promoted', repeat: 'Re-enrolled', demote: 'Demoted' };
      if (res.skipped > 0) {
        toast.success(`Already processed for this year — no change made.`);
      } else {
        toast.success(`${labels[actionMode ?? 'promote'] ?? 'Done'}.`);
      }
      const targetYearId = caYearId;
      actionMode = null; caYearId = ''; caClassId = ''; caError = ''; overrideNeeded = false; overrideError = '';
      // bulkPromoteStudents returns GraduationRecords, not the new class
      // assignment — fetch fresh to find its id and expand that card.
      const assignments = await listClassAssignments(studentId);
      qc.setQueryData(['student-class-assignments', studentId], assignments);
      const newAssignment = assignments.find(a => a.academic_year_id === targetYearId);
      if (newAssignment) onDone(newAssignment.id);
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { overrideNeeded = true; overrideError = detailOf(e) ?? 'This mismatch needs a reason.'; return; }
      caError = detailOf(e) ?? 'Could not assign.';
    },
  });

  function handleAssign() {
    caError = '';
    if (!caYearId)  { caError = 'Select an academic year.'; return; }
    if (!caClassId) { caError = 'Select a class.'; return; }
    $assignMut.mutate(undefined);
  }

  const CARD = {
    promote: { label: 'Promote',     sub: 'Move up a year',        border: 'border-green-200 dark:border-green-800', bg: 'bg-green-50 dark:bg-green-950/30', text: 'text-green-700 dark:text-green-400', sub2: 'text-green-600 dark:text-green-500' },
    repeat:  { label: 'Repeat year', sub: 'Same class, new year',  border: 'border-amber-200 dark:border-amber-800', bg: 'bg-amber-50 dark:bg-amber-950/30', text: 'text-amber-700 dark:text-amber-400', sub2: 'text-amber-600 dark:text-amber-500' },
    demote:  { label: 'Demote',      sub: 'Move down a year',      border: 'border-red-200 dark:border-red-800',     bg: 'bg-red-50 dark:bg-red-950/30',     text: 'text-red-700 dark:text-red-400',    sub2: 'text-red-600 dark:text-red-500'   },
  };
</script>

{#if !actionMode}
  <!-- Year-end action cards — admin-tier (Category D), never a class teacher's own-class job -->
  {#if canManage}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p class="mb-3 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Year-end actions</p>
      {#if currentYearRecord}
        <div class="mb-3 flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
          <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"/></svg>
          <span>
            Already {(OUTCOME_LABEL[currentYearRecord.graduation_type] ?? currentYearRecord.graduation_type).toLowerCase()} for {currentYear?.name}
            (processed {new Date(currentYearRecord.processed_at).toLocaleDateString()}). Using the same year again below will be skipped, not reapplied.
          </span>
        </div>
      {/if}
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {#each Object.entries(CARD) as [key, meta]}
          <button onclick={() => openAction(key as ActionMode)}
            class="rounded-xl border px-3 py-2.5 text-left transition hover:opacity-80 {meta.border} {meta.bg}">
            <p class="text-xs font-semibold {meta.text}">{meta.label}</p>
            <p class="mt-0.5 text-[10px] {meta.sub2}">{meta.sub}</p>
          </button>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Transfer — separate from year-end actions; can happen any time; pastoral (Category A) -->
  <div class="mt-3">
    <TransferOutPanel {studentId} {canEdit} />
  </div>

{:else if actionMode}
  {@const isDemote  = actionMode === 'demote'}
  {@const meta = CARD[actionMode as keyof typeof CARD] ?? CARD.repeat}
  <div class="rounded-2xl border p-5 {meta.border} {meta.bg}">
    <p class="text-sm font-semibold {meta.text}">{meta.label}</p>
    {#if isDemote}
      <p class="mt-1.5 rounded-lg bg-red-100/60 px-3 py-1.5 text-xs font-medium text-red-700 dark:bg-red-950/30 dark:text-red-400">
        Demotion is uncommon. Confirm the target class carefully.
      </p>
    {/if}
    <div class="mt-4 grid gap-3 sm:grid-cols-2">
      <div>
        <label class="text-xs font-medium {meta.text}">Academic year</label>
        <select bind:value={caYearId} class="sel mt-1">
          <option value="">Select year…</option>
          {#each years as y}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
        </select>
      </div>
      <TargetClassPicker
        fromClass={activeClass} {classes}
        value={caClassId} onChange={(id) => caClassId = id} mode={actionMode}
        label="Class" />
    </div>
    {#if caYearId && firstTerm}
      <label class="mt-3 flex cursor-pointer items-center gap-2 text-xs {meta.text}">
        <input type="checkbox" bind:checked={alsoEnroll} class="accent-current" />
        Also register in {firstTerm.name} (first term)
      </label>
    {/if}
    {#if targetYearRecord}
      <p class="mt-3 rounded-lg bg-amber-100/60 px-3 py-1.5 text-xs font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
        Already {(OUTCOME_LABEL[targetYearRecord.graduation_type] ?? targetYearRecord.graduation_type).toLowerCase()} for {targetYear?.name} — confirming again will be skipped, not reapplied.
      </p>
    {/if}
    {#if caError}<p class="mt-2 text-xs text-red-600">{caError}</p>{/if}
    <div class="mt-4 flex gap-2">
      <button onclick={handleAssign} disabled={$assignMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: {isDemote ? '#dc2626' : 'var(--brand)'}">
        {$assignMut.isPending ? 'Saving…' : targetYearRecord ? 'Already processed' : `Confirm ${meta.label}`}
      </button>
      <button onclick={() => { actionMode = null; caError = ''; }}
        class="rounded-xl border border-[var(--border)] bg-white/60 px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-white/80 transition dark:bg-white/5">
        Cancel
      </button>
    </div>
  </div>
{/if}

<OverrideReasonModal
  open={overrideNeeded}
  title="Class mismatch"
  errorMessage={overrideError}
  isPending={$assignMut.isPending}
  onSubmit={(reason) => $assignMut.mutate(reason)}
  onCancel={() => { overrideNeeded = false; overrideError = ''; }}
/>

<style>
  @reference "tailwindcss";
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

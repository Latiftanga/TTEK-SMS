<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    createTransferRequest, listTransfersForStudent, listClassAssignments,
    listGraduationRecords, bulkPromoteStudents, type PromotionRecordCreate,
  } from '$lib/api/students';
  import { type SchoolClass } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';
  import { isSchoolAdmin } from '$lib/stores/permissions';

  interface Props {
    studentId: string;
    activeClass: SchoolClass | null;
    classes: SchoolClass[];
    years: import('$lib/api/academic').AcademicYear[];
    onDone: (newAssignmentId: string) => void;
  }
  const { studentId, activeClass, classes, years, onDone }: Props = $props();

  const qc = useQueryClient();

  const transfersQ = createQuery({
    queryKey: ['student-transfers', studentId],
    queryFn:  () => listTransfersForStudent(studentId),
    staleTime: 30_000,
  });
  const pendingTransfer = $derived(($transfersQ.data ?? []).find(t => t.status === 'PENDING') ?? null);
  const lastTransfer    = $derived(($transfersQ.data ?? [])[0] ?? null);

  // Year-end progression already writes a GraduationRecord via the bulk endpoint
  // (services/promotion.py) — fetch this student's own history so the panel can
  // show "already processed" instead of presenting Promote/Repeat/Demote as if
  // nothing has happened yet, and warn before a duplicate submission that the
  // server would just silently skip.
  const graduationRecordsQ = createQuery({
    queryKey: ['student-graduation-records', studentId],
    queryFn:  () => listGraduationRecords({ student_id: studentId }),
    staleTime: 30_000,
  });
  const currentYear = $derived(years.find(y => y.is_current) ?? null);
  const currentYearRecord = $derived(
    currentYear ? ($graduationRecordsQ.data ?? []).find(r => r.academic_year_id === currentYear.id) ?? null : null
  );
  const OUTCOME_LABEL: Record<string, string> = { PROMOTED: 'Promoted', REPEATED: 'Repeated', DEMOTED: 'Demoted' };

  type ActionMode = 'promote' | 'repeat' | 'demote' | null;
  let actionMode     = $state<ActionMode>(null);
  let showTransfer   = $state(false);
  let caYearId       = $state('');
  let caClassId      = $state('');
  let caError        = $state('');
  let alsoEnroll     = $state(true);
  let transferReason = $state('');
  let transferErr    = $state('');

  const targetYear = $derived(years.find(y => y.id === caYearId) ?? null);
  const firstTerm  = $derived([...(targetYear?.terms ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date))[0] ?? null);
  const targetYearRecord = $derived(
    caYearId ? ($graduationRecordsQ.data ?? []).find(r => r.academic_year_id === caYearId) ?? null : null
  );

  function openAction(mode: ActionMode) {
    actionMode = mode; caYearId = ''; caError = ''; alsoEnroll = true;
    if (!activeClass) { caClassId = ''; return; }
    if (mode === 'promote') {
      caClassId = classes.find(
        c => c.level === activeClass.level
          && c.year_group === activeClass.year_group + 1
          && c.programme_id === activeClass.programme_id
          && (c.stream ?? null) === (activeClass.stream ?? null)
      )?.id ?? '';
    } else if (mode === 'repeat') {
      caClassId = activeClass.id;
    } else if (mode === 'demote') {
      caClassId = classes.find(
        c => c.level === activeClass.level
          && c.year_group === activeClass.year_group - 1
          && c.programme_id === activeClass.programme_id
          && (c.stream ?? null) === (activeClass.stream ?? null)
      )?.id ?? '';
    } else {
      caClassId = '';
    }
  }

  const ACTION_TO_TYPE: Record<'promote' | 'repeat' | 'demote', PromotionRecordCreate['graduation_type']> = {
    promote: 'PROMOTED', repeat: 'REPEATED', demote: 'DEMOTED',
  };

  const assignMut = createMutation({
    mutationFn: () => bulkPromoteStudents({
      academic_year_id: caYearId,
      academic_term_id: alsoEnroll && firstTerm ? firstTerm.id : null,
      records: [{ student_id: studentId, class_id: caClassId, graduation_type: ACTION_TO_TYPE[actionMode ?? 'promote'] }],
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
      actionMode = null; caYearId = ''; caClassId = ''; caError = '';
      // bulkPromoteStudents returns GraduationRecords, not the new class
      // assignment — fetch fresh to find its id and expand that card.
      const assignments = await listClassAssignments(studentId);
      qc.setQueryData(['student-class-assignments', studentId], assignments);
      const newAssignment = assignments.find(a => a.academic_year_id === targetYearId);
      if (newAssignment) onDone(newAssignment.id);
    },
    onError: (e: unknown) => { caError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not assign.'; },
  });

  const transferMut = createMutation({
    mutationFn: () => createTransferRequest(studentId, { reason: transferReason.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-transfers', studentId] });
      showTransfer = false; transferReason = ''; transferErr = ''; toast.success('Transfer request submitted for review.');
    },
    onError: (e: unknown) => { transferErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create transfer.'; },
  });

  function handleAssign() {
    caError = '';
    if (!caYearId)  { caError = 'Select an academic year.'; return; }
    if (!caClassId) { caError = 'Select a class.'; return; }
    $assignMut.mutate();
  }

  const CARD = {
    promote: { label: 'Promote',     sub: 'Move up a year',        border: 'border-green-200 dark:border-green-800', bg: 'bg-green-50 dark:bg-green-950/30', text: 'text-green-700 dark:text-green-400', sub2: 'text-green-600 dark:text-green-500' },
    repeat:  { label: 'Repeat year', sub: 'Same class, new year',  border: 'border-amber-200 dark:border-amber-800', bg: 'bg-amber-50 dark:bg-amber-950/30', text: 'text-amber-700 dark:text-amber-400', sub2: 'text-amber-600 dark:text-amber-500' },
    demote:  { label: 'Demote',      sub: 'Move down a year',      border: 'border-red-200 dark:border-red-800',     bg: 'bg-red-50 dark:bg-red-950/30',     text: 'text-red-700 dark:text-red-400',    sub2: 'text-red-600 dark:text-red-500'   },
  };
</script>

{#if !actionMode && !showTransfer}
  <!-- Year-end action cards -->
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

  <!-- Transfer — separate from year-end actions; can happen any time -->
  <div class="mt-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <p class="mb-3 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Transfer to another school</p>
    {#if pendingTransfer}
      <div class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-800 dark:bg-amber-950/30">
        <div>
          <p class="text-xs font-semibold text-amber-800 dark:text-amber-200">Transfer request pending review</p>
          <p class="mt-0.5 text-[10px] text-amber-700 dark:text-amber-400">
            Submitted {new Date(pendingTransfer.created_at).toLocaleDateString()}{pendingTransfer.reason ? ` — ${pendingTransfer.reason}` : ''}
          </p>
        </div>
        {#if $isSchoolAdmin}
          <a href="/admin/transfers" class="shrink-0 text-xs font-medium text-amber-800 underline hover:no-underline dark:text-amber-200">
            View in transfer queue →
          </a>
        {/if}
      </div>
    {:else}
      {#if lastTransfer && lastTransfer.status !== 'PENDING'}
        <p class="mb-2 text-[10px] text-[var(--fg-muted)]">
          Last request: {lastTransfer.status.charAt(0) + lastTransfer.status.slice(1).toLowerCase()}
          {#if lastTransfer.reviewed_at} on {new Date(lastTransfer.reviewed_at).toLocaleDateString()}{/if}
        </p>
      {/if}
      <button onclick={() => showTransfer = true}
        class="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-left transition hover:border-[var(--fg-subtle)]">
        <p class="text-xs font-semibold text-[var(--fg)]">Transfer out</p>
        <p class="mt-0.5 text-[10px] text-[var(--fg-muted)]">Leave this school</p>
      </button>
    {/if}
  </div>

{:else if actionMode}
  {@const isPromote = actionMode === 'promote'}
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
      <div>
        <label class="text-xs font-medium {meta.text}">Class
          {#if isPromote && caClassId}
            <span class="ml-1 rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-950/40 dark:text-green-300">suggested</span>
          {/if}
        </label>
        <select bind:value={caClassId} class="sel mt-1">
          <option value="">Select class…</option>
          {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
        </select>
      </div>
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

{:else if showTransfer}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="text-sm font-semibold text-[var(--fg)]">Transfer out</p>
    <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Creates a request for admin review. Approval marks this student inactive.</p>
    <div class="mt-4">
      <label class="block text-xs font-medium text-[var(--fg-muted)]">Reason (optional)</label>
      <textarea bind:value={transferReason} rows="2" placeholder="e.g. Relocating to Accra"
        class="mt-1 w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition"></textarea>
    </div>
    {#if transferErr}<p class="mt-2 text-xs text-red-500">{transferErr}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={() => $transferMut.mutate()} disabled={$transferMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: var(--brand)">
        {$transferMut.isPending ? 'Submitting…' : 'Submit transfer request'}
      </button>
      <button onclick={() => { showTransfer = false; transferReason = ''; transferErr = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
        Cancel
      </button>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

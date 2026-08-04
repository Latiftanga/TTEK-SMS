<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listClasses, listYears, type SchoolClass, type AcademicYear } from '$lib/api/academic';
  import { listStudents, listGraduationRecords, bulkPromoteStudents, type PromotionRecordCreate } from '$lib/api/students';
  import { writable } from 'svelte/store';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import { detailOf, isLocked } from '$lib/apiError';
  import { reactiveQuery } from '$lib/query.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import TargetClassPicker from '$lib/components/TargetClassPicker.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';
  import PromoteStudentList from './PromoteStudentList.svelte';

  const qc = useQueryClient();
  setPageTitle('Promotion');

  const classesQ = createQuery({ queryKey: ['classes'],        queryFn: listClasses, staleTime: 5 * 60_000 });
  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });

  // ── Selections ────────────────────────────────────────────────────────────────
  let fromClassId = $state('');
  let toClassId   = $state('');
  let toYearId    = $state('');
  let alsoEnroll  = $state(true); // also register in first term of target year

  const classes = $derived<SchoolClass[]>($classesQ.data ?? []);
  const years   = $derived<AcademicYear[]>(
    [...($yearsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date))
  );

  const fromClass = $derived(classes.find(c => c.id === fromClassId) ?? null);

  // First term of target year (for enroll-on-promote)
  const targetYear = $derived(years.find(y => y.id === toYearId));
  const firstTerm  = $derived(
    [...(targetYear?.terms ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date))[0] ?? null
  );

  // Which students already have a GraduationRecord for the target year —
  // surfaced per-row so staff aren't selecting blind and only learning who
  // got skipped after submitting.
  const gradRecordsQ = reactiveQuery(() => ({
    queryKey: ['student-graduation-records', 'year', toYearId] as const,
    queryFn:  () => listGraduationRecords({ academic_year_id: toYearId }),
    enabled:  !!toYearId,
    staleTime: 30_000,
  }));
  const alreadyProcessed = $derived(new Set(($gradRecordsQ.data ?? []).map(r => r.student_id)));

  // ── Load students from source class ──────────────────────────────────────────
  const studentOpts = writable({
    queryKey: ['students', 'class', fromClassId] as const,
    queryFn: () => listStudents({ class_id: fromClassId, active_only: true }),
    enabled: false,
    staleTime: 60_000,
  });
  $effect(() => {
    const cid = fromClassId;
    studentOpts.set({
      queryKey: ['students', 'class', cid] as const,
      queryFn: () => listStudents({ class_id: cid, active_only: true }),
      enabled: !!cid,
      staleTime: 60_000,
    });
  });
  const studentsQ = createQuery(studentOpts);
  const students  = $derived($studentsQ.data ?? []);

  // ── Selection ─────────────────────────────────────────────────────────────────
  let selected = $state(new Set<string>());

  $effect(() => {
    // Clear selection when source class changes
    void fromClassId; selected = new Set();
  });

  const allSelected = $derived(students.length > 0 && selected.size === students.length);

  function toggleAll() {
    selected = allSelected ? new Set() : new Set(students.map(s => s.id));
  }
  function toggleOne(id: string) {
    const s = new Set(selected);
    s.has(id) ? s.delete(id) : s.add(id);
    selected = s;
  }

  // ── Promote mutation ──────────────────────────────────────────────────────────
  type ActionType = 'promote' | 'repeat' | 'demote';
  const ACTION_TO_TYPE: Record<ActionType, PromotionRecordCreate['graduation_type']> = {
    promote: 'PROMOTED', repeat: 'REPEATED', demote: 'DEMOTED',
  };
  let actionType: ActionType = $state('promote');
  let confirmOpen = $state(false);
  let promoteErr  = $state('');
  let overrideNeeded = $state(false);
  let overrideError  = $state('');

  // Reset the target class whenever the source class or action type changes,
  // so TargetClassPicker re-suggests fresh rather than carrying over a
  // choice made for a different context.
  $effect(() => { void fromClassId; void actionType; toClassId = ''; });

  const promoteMut = createMutation({
    mutationFn: (overrideReason?: string) => {
      const records: PromotionRecordCreate[] = [...selected].map(sid => ({
        student_id: sid, class_id: toClassId, graduation_type: ACTION_TO_TYPE[actionType],
      }));
      return bulkPromoteStudents({
        academic_year_id: toYearId,
        academic_term_id: alsoEnroll && firstTerm ? firstTerm.id : null,
        records,
        override_reason: overrideReason,
      });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['students', 'class', fromClassId] });
      qc.invalidateQueries({ queryKey: ['student-class-assignments'] });
      const label = actionType === 'promote' ? 'Promoted' : actionType === 'repeat' ? 'Re-enrolled' : 'Demoted';
      toast.success(`${label}: ${res.processed} student(s). Skipped: ${res.skipped} (already processed for this year).`);
      selected = new Set(); confirmOpen = false; promoteErr = ''; overrideNeeded = false; overrideError = '';
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { overrideNeeded = true; overrideError = detailOf(e) ?? 'This mismatch needs a reason.'; return; }
      promoteErr = detailOf(e) ?? 'Could not complete operation.';
      confirmOpen = false;
    },
  });

  function handlePromote() {
    promoteErr = '';
    if (!fromClassId) { promoteErr = 'Select a source class.'; return; }
    if (!toClassId)   { promoteErr = 'Select a target class.'; return; }
    if (!toYearId)    { promoteErr = 'Select a target academic year.'; return; }
    if (selected.size === 0) { promoteErr = 'Select at least one student.'; return; }
    confirmOpen = true;
  }

  const ACTION_LABELS: Record<ActionType, { label: string; color: string; desc: string }> = {
    promote: { label: 'Promote',     color: 'text-green-600 dark:text-green-400',  desc: 'Move up to the next year group' },
    repeat:  { label: 'Repeat year', color: 'text-amber-600 dark:text-amber-400',  desc: 'Re-enroll in the same class for a new year' },
    demote:  { label: 'Demote',      color: 'text-red-600 dark:text-red-400',      desc: 'Move down to a lower year group' },
  };
</script>


<PageHeader title="Class Promotion" description="Move students from one class to the next year group. Also registers them in the first term of the target year." />

<div class="space-y-6">
  <!-- Action type selector -->
  <div class="flex gap-2">
    {#each Object.entries(ACTION_LABELS) as [key, meta]}
      <button onclick={() => { actionType = key as ActionType; }}
        class="flex-1 rounded-xl border px-4 py-3 text-left transition
               {actionType === key
                 ? 'border-[var(--brand)] bg-[var(--brand)]/5 ring-1 ring-[var(--brand)]'
                 : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--brand)]/40'}">
        <p class="text-sm font-semibold {actionType === key ? meta.color : 'text-[var(--fg)]'}">{meta.label}</p>
        <p class="mt-0.5 text-[11px] text-[var(--fg-muted)]">{meta.desc}</p>
      </button>
    {/each}
  </div>

  <!-- Config card -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="grid gap-4 sm:grid-cols-2">
      <!-- From -->
      <div class="space-y-3 rounded-xl border border-[var(--border)] p-4">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">From</p>
        <div>
          <label class="lx">Source class</label>
          <select bind:value={fromClassId} class="sel mt-1">
            <option value="">Select class…</option>
            {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
          </select>
        </div>
      </div>

      <!-- To -->
      <div class="space-y-3 rounded-xl border border-[var(--border)] p-4">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">To</p>
        <div>
          <label class="lx">Target academic year</label>
          <select bind:value={toYearId} class="sel mt-1">
            <option value="">Select year…</option>
            {#each years as y}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
          </select>
        </div>
        <TargetClassPicker
          {fromClass} {classes}
          value={toClassId} onChange={(id) => toClassId = id} mode={actionType}
          label="Target class" />
      </div>
    </div>

    <!-- Also enroll in first term -->
    {#if toYearId && firstTerm}
      <label class="mt-4 flex cursor-pointer items-center gap-2.5">
        <input type="checkbox" bind:checked={alsoEnroll} class="h-4 w-4 rounded accent-[var(--brand)]" />
        <span class="text-sm text-[var(--fg)]">
          Also register students in <strong>{firstTerm.name}</strong> (first term of selected year)
        </span>
      </label>
    {/if}
  </div>

  <!-- Student list -->
  {#if !fromClassId}
    <div class="rounded-2xl border border-dashed border-[var(--border)] py-12 text-center">
      <p class="text-sm text-[var(--fg-muted)]">Select a source class to see students.</p>
    </div>
  {:else if $studentsQ.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if students.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] py-12 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No active students found in this class.</p>
    </div>
  {:else}
    <PromoteStudentList {students} {selected} {alreadyProcessed} onToggleOne={toggleOne} onToggleAll={toggleAll} onClear={() => selected = new Set()} />

    <!-- Action bar -->
    {#if promoteErr}
      <p class="rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">{promoteErr}</p>
    {/if}

    {#if !confirmOpen}
      <button onclick={handlePromote} disabled={selected.size === 0}
        class="w-full rounded-xl py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
        style="background: var(--brand)">
        {ACTION_LABELS[actionType].label} {selected.size > 0 ? `${selected.size} student${selected.size > 1 ? 's' : ''}` : 'selected'} →
      </button>
    {:else}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
        <p class="text-sm font-semibold text-[var(--fg)]">Confirm {ACTION_LABELS[actionType].label.toLowerCase()}</p>
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          Move <strong>{selected.size}</strong> student{selected.size > 1 ? 's' : ''} from
          <strong>{fromClass?.display_name}</strong> →
          <strong>{classes.find(c => c.id === toClassId)?.display_name ?? '—'}</strong>
          ({years.find(y => y.id === toYearId)?.name ?? '—'})
          {#if alsoEnroll && firstTerm}, then register in <strong>{firstTerm.name}</strong>{/if}.
        </p>
        {#if actionType === 'demote'}
          <p class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
            Demotion is uncommon. Double-check the target class before confirming.
          </p>
        {/if}
        <div class="mt-4 flex gap-2">
          <button onclick={() => $promoteMut.mutate(undefined)} disabled={$promoteMut.isPending}
            class="rounded-xl px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background: {actionType === 'demote' ? '#dc2626' : 'var(--brand)'}">
            {$promoteMut.isPending ? 'Processing…' : `Confirm ${ACTION_LABELS[actionType].label}`}
          </button>
          <button onclick={() => { confirmOpen = false; promoteErr = ''; }}
            class="rounded-xl border border-[var(--border)] px-5 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      </div>
    {/if}
  {/if}
</div>

<OverrideReasonModal
  open={overrideNeeded}
  title="Class mismatch"
  errorMessage={overrideError}
  isPending={$promoteMut.isPending}
  onSubmit={(reason) => $promoteMut.mutate(reason)}
  onCancel={() => { overrideNeeded = false; overrideError = ''; }}
/>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

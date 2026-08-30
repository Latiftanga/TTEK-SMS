<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import {
    listClassSubjects, listSubjects, removeClassSubject, updateClassSubject,
    listYears, listSubjectTeachers, type ClassSubject,
  } from '$lib/api/academic';
  import { listStaff } from '$lib/api/staff';
  import { findCurrentYear, findCurrentTerm, flattenTerms } from '$lib/academicPeriod';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import { school } from '$lib/stores/school';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import BulkRegisterCoreSubjectsButton from './BulkRegisterCoreSubjectsButton.svelte';
  import AddClassSubjectForm from './AddClassSubjectForm.svelte';
  import SubjectClassManagementPanel from './SubjectClassManagementPanel.svelte';

  interface Props { classId: string; classActive: boolean; }
  const { classId, classActive }: Props = $props();

  // Elective subjects are an SHS-programme concept (e.g. French vs
  // Literature-in-French) — Basic schools follow a fixed GES curriculum with
  // no per-student subject choice, so the Core/Elective toggle would just be
  // confusing noise for them. Every subject already defaults to non-elective,
  // so hiding the control changes nothing functionally for Basic schools.
  const showElectiveToggle = $derived($school?.schoolType !== 'BASIC');

  const qc = useQueryClient();

  const yearsQ   = createQuery({ queryKey: ['academic-years'],          queryFn: listYears,                                        staleTime: 5 * 60_000 });
  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId),                 staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],                queryFn: listSubjects,                                     staleTime: 5 * 60_000 });
  const staffQ   = createQuery({ queryKey: ['staff'],                   queryFn: () => listStaff({ limit: 200, active_only: true }), staleTime: 5 * 60_000 });

  // ── Year selection ───────────────────────────────────────────────────────────
  // SubjectTeacher is scoped to the academic year, not the term — one
  // assignment covers the whole year, matching ClassTeacher's convention.
  let yearId = $state('');
  $effect(() => {
    if (yearId) return;
    const cur = findCurrentYear($yearsQ.data ?? []);
    if (cur) yearId = cur.id;
  });
  // Passed to SubjectClassManagementPanel purely so it can invalidate the
  // catalogue page's ['subject-summary', subjectId, termId] cache when a
  // roster changes here — '' (no current term) is harmless, it just won't
  // match any cached key.
  const currentTermId = $derived(findCurrentTerm(flattenTerms($yearsQ.data ?? []))?.id ?? '');

  // Which subject row is expanded for inline teacher + roster management.
  let expandedSubjectId = $state<string | null>(null);

  // Writable store pattern — avoids TanStack's queryKey validation on mount
  const subjTeachersOpts = writable({ queryKey: ['subject-teachers', classId, ''] as string[], queryFn: () => listSubjectTeachers(classId, ''), enabled: false, staleTime: 60_000 });
  $effect(() => {
    const y = yearId;
    subjTeachersOpts.set({ queryKey: ['subject-teachers', classId, y], queryFn: () => listSubjectTeachers(classId, y), enabled: !!y, staleTime: 60_000 });
  });
  const subjTeachersQ = createQuery(subjTeachersOpts);

  // ── Derived ───────────────────────────────────────────────────────────────────
  const classSubjects    = $derived($clsSubjQ.data ?? []);
  const subjectMap       = $derived(new Map(($allSubjQ.data ?? []).map(s => [s.id, s])));
  const staffMap         = $derived(new Map(($staffQ.data ?? []).map(s => [s.id, s])));
  const teacherBySubject = $derived(new Map(($subjTeachersQ.data ?? []).map(st => [st.subject_id, st.staff_member_id])));
  const unassignedSubjs  = $derived(($allSubjQ.data ?? []).filter(s => s.is_active && !classSubjects.some(cs => cs.subject_id === s.id)));
  const unassignedCount  = $derived(classSubjects.filter(cs => yearId && !teacherBySubject.has(cs.subject_id)).length);
  // Grouping for the Core/Elective sections below — the whole-class bulk
  // register button lives with the core group (it never touches electives),
  // electives are managed one subject at a time via their own row.
  const coreSubjects     = $derived(classSubjects.filter(cs => !cs.is_elective));
  const electiveSubjects = $derived(classSubjects.filter(cs => cs.is_elective));

  // ── Add subject ───────────────────────────────────────────────────────────────
  let showAdd = $state(false);

  // ── Remove subject ────────────────────────────────────────────────────────────
  let confirmRemoveId = $state<string | null>(null);
  const removeMut = createMutation({
    mutationFn: (subjectId: string) => removeClassSubject(classId, subjectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, yearId] });
      toast.success('Subject removed.');
    },
    onError: (e) => toast.error(apiError(e, 'Failed to remove subject.')),
  });

  // ── Elective toggle ───────────────────────────────────────────────────────────
  // False (default) = every student takes it, included in the "register
  // non-elective subjects" bulk action. True = a genuine per-student choice,
  // left out of that action — registered individually on the student's own
  // Enrollment tab instead.
  const electiveMut = createMutation({
    mutationFn: (args: { subjectId: string; isElective: boolean }) =>
      updateClassSubject(classId, args.subjectId, { is_elective: args.isElective }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['class-subjects', classId] }),
    onError: (e) => toast.error(apiError(e, 'Failed to update subject.')),
  });

  // Avatar helpers
  const COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#ec4899','#14b8a6','#f97316'];
  function avatarBg(name: string): string {
    let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) & 0xff;
    return COLORS[h % COLORS.length];
  }
  function initials(name: string): string {
    const p = name.trim().split(/\s+/);
    return (p[0][0] + (p[1]?.[0] ?? '')).toUpperCase();
  }

  const selSm = 'rounded-xl border border-[var(--border)] bg-[var(--bg)] py-1.5 pl-2.5 pr-7 text-xs text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition appearance-none';
</script>

<div class="space-y-4">
  {#if $clsSubjQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>

  {:else if classSubjects.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-12 text-center">
      <svg class="mx-auto mb-3 h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.25" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>
      </svg>
      <p class="text-sm font-medium text-[var(--fg-muted)]">No subjects assigned yet.</p>
      {#if classActive}
        <button onclick={() => showAdd = true}
          class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background: var(--brand)">Add first subject</button>
      {:else}
        <p class="mt-3 text-xs text-[var(--fg-subtle)]">This class is inactive — reactivate it before adding subjects.</p>
      {/if}
    </div>

  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <!-- Card header: count + unassigned warning + term selector + add button -->
      <div class="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div class="flex flex-1 flex-wrap items-center gap-2">
          <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
            {classSubjects.length} subject{classSubjects.length !== 1 ? 's' : ''}
          </p>
          {#if yearId && unassignedCount > 0}
            <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
              {unassignedCount} without teacher
            </span>
          {/if}
        </div>
        <!-- Year selector (compact, inline) -->
        <div class="relative shrink-0">
          <select bind:value={yearId} class={selSm}>
            <option value="">No year</option>
            {#each $yearsQ.data ?? [] as y (y.id)}
              <option value={y.id}>{y.name}{y.is_current ? ' ✓' : ''}</option>
            {/each}
          </select>
          <svg class="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
          </svg>
        </div>
        {#if classActive}
          <button onclick={() => showAdd = !showAdd}
            class="flex shrink-0 items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
            </svg>
            Add
          </button>
        {:else}
          <span class="shrink-0 text-[10px] font-semibold text-[var(--fg-subtle)]">Class inactive</span>
        {/if}
      </div>

      <!-- Subject row -->
      {#snippet subjectRow(cs: ClassSubject)}
        {@const subj    = subjectMap.get(cs.subject_id)}
        {@const staffId = teacherBySubject.get(cs.subject_id)}
        {@const teacher = staffId ? staffMap.get(staffId) : null}

        <div class="border-b border-[var(--border)] last:border-0">
          <div class="flex items-center gap-3 px-4 py-3">
            <!-- Subject name + code -->
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-[var(--fg)]">{subj?.name ?? '—'}</p>
              {#if subj?.code}
                <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{subj.code}</p>
              {/if}
            </div>

            <!-- Elective toggle (SHS-only — Basic has no per-student subject choice) -->
            {#if showElectiveToggle}
              <button onclick={() => $electiveMut.mutate({ subjectId: cs.subject_id, isElective: !cs.is_elective })}
                disabled={$electiveMut.isPending}
                title="Click to toggle — non-elective subjects are included in the bulk 'register non-elective subjects' action"
                class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold transition disabled:opacity-40
                  {cs.is_elective
                    ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400'
                    : 'bg-[var(--hover)] text-[var(--fg-subtle)]'}">
                {cs.is_elective ? 'Elective' : 'Core'}
              </button>
            {/if}

            <!-- Teacher chip -->
            {#if !yearId}
              <span class="shrink-0 text-xs text-[var(--fg-subtle)]">—</span>
            {:else if $subjTeachersQ.isPending}
              <div class="h-4 w-28 animate-pulse rounded-full bg-[var(--hover)]"></div>
            {:else if teacher}
              <div class="flex shrink-0 items-center gap-1.5">
                <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[8px] font-bold text-white"
                     style="background: {avatarBg(teacher.display_name)}">
                  {initials(teacher.display_name)}
                </div>
                <span class="max-w-[120px] truncate text-xs font-medium text-[var(--fg-muted)]">{teacher.display_name}</span>
              </div>
            {:else}
              <span class="shrink-0 rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">No teacher</span>
            {/if}

            <!-- Actions -->
            <button onclick={() => expandedSubjectId = expandedSubjectId === cs.subject_id ? null : cs.subject_id}
              class="flex min-h-[44px] shrink-0 items-center px-2 text-xs font-medium transition hover:underline" style="color:var(--brand)">
              {expandedSubjectId === cs.subject_id ? 'Hide' : 'Manage teacher & students'}
            </button>
            <button onclick={() => confirmRemoveId = cs.subject_id} disabled={$removeMut.isPending}
              class="flex min-h-[44px] shrink-0 items-center px-2 text-xs text-[var(--fg-subtle)] transition hover:text-red-500 disabled:opacity-40">
              Remove
            </button>
          </div>
          {#if expandedSubjectId === cs.subject_id}
            <SubjectClassManagementPanel subjectId={cs.subject_id} {classId} {yearId} termId={currentTermId} classSubjectId={cs.id} />
          {/if}
        </div>
      {/snippet}

      <!-- Grouped by core/elective — SHS only, since Basic has no elective
           concept exposed anywhere else in this tab either (see
           showElectiveToggle above). -->
      {#if showElectiveToggle}
        {#if coreSubjects.length > 0}
          <div class="flex items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--hover)]/20 px-4 py-2">
            <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Core subjects</p>
            {#if classActive}<BulkRegisterCoreSubjectsButton {classId} />{/if}
          </div>
          {#each coreSubjects as cs (cs.subject_id)}{@render subjectRow(cs)}{/each}
        {/if}
        {#if electiveSubjects.length > 0}
          <div class="border-b border-[var(--border)] bg-[var(--hover)]/20 px-4 py-2">
            <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Elective subjects</p>
          </div>
          {#each electiveSubjects as cs (cs.subject_id)}{@render subjectRow(cs)}{/each}
        {/if}
      {:else}
        {#if classActive && classSubjects.length > 0}
          <div class="border-b border-[var(--border)] bg-[var(--hover)]/20 px-4 py-2">
            <BulkRegisterCoreSubjectsButton {classId} />
          </div>
        {/if}
        {#each classSubjects as cs (cs.subject_id)}{@render subjectRow(cs)}{/each}
      {/if}
    </div>
  {/if}

  <!-- Add subject form -->
  {#if showAdd && classActive}
    <AddClassSubjectForm {classId} {unassignedSubjs} onClose={() => showAdd = false} />
  {/if}
</div>

<ConfirmModal
  open={!!confirmRemoveId}
  title="Remove subject?"
  message="This subject and its teacher assignment will be removed from the class. The subject itself is not deleted."
  confirmLabel="Remove"
  isPending={$removeMut.isPending}
  onConfirm={() => { $removeMut.mutate(confirmRemoveId!); confirmRemoveId = null; }}
  onCancel={() => confirmRemoveId = null}
/>

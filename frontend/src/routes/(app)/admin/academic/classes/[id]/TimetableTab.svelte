<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import {
    listClassSubjects, listSubjects, listYears, listSubjectTeachers,
  } from '$lib/api/academic';
  import { listPeriods, type SchoolPeriod } from '$lib/api/schoolPeriods';
  import { getClassTimetable, upsertTimetableSlot, deleteTimetableSlot } from '$lib/api/timetable';
  import type { DayOfWeek } from '$lib/api/attendance';
  import { findCurrentYear } from '$lib/academicPeriod';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { classId: string; classActive: boolean; }
  const { classId, classActive }: Props = $props();

  const qc = useQueryClient();

  const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  const DAY_LABELS: Record<DayOfWeek, string> = {
    MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
    THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday', SUN: 'Sunday',
  };
  let selectedDay = $state<DayOfWeek>('MON');

  const yearsQ    = createQuery({ queryKey: ['academic-years'],          queryFn: listYears,                       staleTime: 5 * 60_000 });
  const periodsQ  = createQuery({ queryKey: ['school-periods'],          queryFn: listPeriods,                     staleTime: 60_000 });
  const clsSubjQ  = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });
  const allSubjQ  = createQuery({ queryKey: ['subjects'],                queryFn: listSubjects,                    staleTime: 5 * 60_000 });

  let yearId = $state('');
  $effect(() => {
    if (yearId) return;
    const cur = findCurrentYear($yearsQ.data ?? []);
    if (cur) yearId = cur.id;
  });

  const timetableOpts = writable({
    queryKey: ['class-timetable', classId, ''] as string[],
    queryFn: () => getClassTimetable(classId, ''), enabled: false, staleTime: 30_000,
  });
  $effect(() => {
    const y = yearId;
    timetableOpts.set({
      queryKey: ['class-timetable', classId, y],
      queryFn: () => getClassTimetable(classId, y), enabled: !!y, staleTime: 30_000,
    });
  });
  const timetableQ = createQuery(timetableOpts);

  const subjTeachersOpts = writable({
    queryKey: ['subject-teachers', classId, ''] as string[],
    queryFn: () => listSubjectTeachers(classId, ''), enabled: false, staleTime: 60_000,
  });
  $effect(() => {
    const y = yearId;
    subjTeachersOpts.set({
      queryKey: ['subject-teachers', classId, y],
      queryFn: () => listSubjectTeachers(classId, y), enabled: !!y, staleTime: 60_000,
    });
  });
  const subjTeachersQ = createQuery(subjTeachersOpts);

  const subjectMap       = $derived(new Map(($allSubjQ.data ?? []).map(s => [s.id, s])));
  const classSubjects    = $derived($clsSubjQ.data ?? []);
  const teacherBySubject = $derived(new Set(($subjTeachersQ.data ?? []).map(st => st.subject_id)));
  const slotByPeriod      = $derived(new Map(($timetableQ.data ?? []).map(s => [s.period_id, s])));
  const dayPeriods        = $derived(
    ($periodsQ.data ?? [])
      .filter((p: SchoolPeriod) => p.day_of_week === selectedDay)
      .sort((a, b) => a.period_number - b.period_number)
  );

  function invalidateTimetable() {
    qc.invalidateQueries({ queryKey: ['class-timetable', classId, yearId] });
  }

  // ── Assign / change ──────────────────────────────────────────────────────
  let assigningPeriodId = $state<string | null>(null);
  let pickedSubjectId   = $state('');
  let assignError       = $state('');

  function startAssign(periodId: string, currentSubjectId?: string) {
    assigningPeriodId = periodId;
    pickedSubjectId = currentSubjectId ?? '';
    assignError = '';
  }

  const assignMut = createMutation({
    mutationFn: () => upsertTimetableSlot(classId, assigningPeriodId!, yearId, pickedSubjectId),
    onSuccess: () => {
      invalidateTimetable();
      assigningPeriodId = null;
      toast.success('Timetable updated.');
    },
    onError: (e) => { assignError = apiError(e, 'Could not assign subject.'); },
  });

  // ── Remove ───────────────────────────────────────────────────────────────
  let confirmRemovePeriodId = $state<string | null>(null);
  const removeMut = createMutation({
    mutationFn: (periodId: string) => deleteTimetableSlot(classId, periodId, yearId),
    onSuccess: () => { invalidateTimetable(); toast.success('Slot cleared.'); },
    onError: (e) => toast.error(apiError(e, 'Could not clear slot.')),
  });
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <p class="text-xs text-[var(--fg-muted)]">Assign a subject to each bell period — the teacher shown is whoever is already assigned to teach that subject for this class.</p>
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
  {:else}
    <!-- Day tabs -->
    <div class="flex gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {#each DAYS as day}
        <button onclick={() => selectedDay = day}
          class="min-h-[44px] shrink-0 rounded-xl px-3 text-xs font-semibold transition
            {selectedDay === day ? 'text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}"
          style={selectedDay === day ? 'background:var(--brand)' : ''}>
          {DAY_LABELS[day].slice(0, 3)}
        </button>
      {/each}
    </div>

    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      {#if $periodsQ.isPending || $timetableQ.isPending}
        <div class="space-y-2 p-4">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
      {:else if dayPeriods.length === 0}
        <p class="p-6 text-center text-sm text-[var(--fg-muted)]">
          No bell periods defined for {DAY_LABELS[selectedDay]} yet — set them up on the
          <a href="/attendance/schedule" class="underline" style="color:var(--brand)">Attendance Schedule</a> page.
        </p>
      {:else}
        <div class="divide-y divide-[var(--border)]">
          {#each dayPeriods as p (p.id)}
            {@const slot = slotByPeriod.get(p.id)}
            <div class="p-3">
              <div class="flex items-center gap-3">
                <div class="w-24 shrink-0">
                  <p class="text-xs font-semibold text-[var(--fg)]">{p.name}</p>
                  <p class="text-[10px] text-[var(--fg-muted)]">{p.start_time.slice(0,5)}–{p.end_time.slice(0,5)}</p>
                </div>
                {#if assigningPeriodId === p.id}
                  <select bind:value={pickedSubjectId} class="sel min-w-0 flex-1 text-sm">
                    <option value="" disabled>Choose a subject…</option>
                    {#each classSubjects as cs (cs.subject_id)}
                      <option value={cs.subject_id} disabled={!teacherBySubject.has(cs.subject_id)}>
                        {subjectMap.get(cs.subject_id)?.name ?? '—'}{!teacherBySubject.has(cs.subject_id) ? ' (no teacher assigned)' : ''}
                      </option>
                    {/each}
                  </select>
                  <button onclick={() => $assignMut.mutate()} disabled={!pickedSubjectId || $assignMut.isPending}
                    class="min-h-[44px] shrink-0 rounded-lg px-3 text-xs font-semibold text-white disabled:opacity-50" style="background:var(--brand)">
                    {$assignMut.isPending ? '…' : 'Save'}
                  </button>
                  <button onclick={() => assigningPeriodId = null}
                    class="min-h-[44px] shrink-0 rounded-lg border border-[var(--border)] px-3 text-xs text-[var(--fg-muted)]">Cancel</button>
                {:else if slot}
                  <div class="min-w-0 flex-1">
                    <p class="truncate text-sm font-medium text-[var(--fg)]">{slot.subject_name}</p>
                    <p class="truncate text-xs text-[var(--fg-muted)]">{slot.teacher_name ?? 'No teacher assigned'}</p>
                  </div>
                  {#if classActive}
                    <button onclick={() => startAssign(p.id, slot.subject_id)}
                      class="min-h-[44px] shrink-0 px-2 text-xs font-medium transition hover:underline" style="color:var(--brand)">Change</button>
                    <button onclick={() => confirmRemovePeriodId = p.id}
                      class="min-h-[44px] shrink-0 px-2 text-xs text-[var(--fg-subtle)] transition hover:text-red-500">Clear</button>
                  {/if}
                {:else}
                  <p class="flex-1 text-sm text-[var(--fg-subtle)]">Not assigned</p>
                  {#if classActive}
                    <button onclick={() => startAssign(p.id)}
                      class="min-h-[44px] shrink-0 rounded-lg border border-[var(--border)] px-3 text-xs font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
                      Assign
                    </button>
                  {/if}
                {/if}
              </div>
              {#if assigningPeriodId === p.id && assignError}
                <p class="mt-1.5 text-xs text-red-500">{assignError}</p>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<ConfirmModal
  open={!!confirmRemovePeriodId}
  title="Clear this slot?"
  message="This period will no longer have a subject assigned for this class."
  confirmLabel="Clear"
  isPending={$removeMut.isPending}
  onConfirm={() => { $removeMut.mutate(confirmRemovePeriodId!); confirmRemovePeriodId = null; }}
  onCancel={() => confirmRemovePeriodId = null}
/>

<style>
  @reference "tailwindcss";
  .sel { @apply min-h-[44px] rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listSchedule, upsertSchedule, type DayOfWeek, type ScheduleDay } from '$lib/api/attendance';
  import { getMySchool, updateMySchool } from '$lib/api/schools';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import PeriodsSection from './PeriodsSection.svelte';

  const qc = useQueryClient();
  setPageTitle('Attendance Schedule');
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  const schedQ = createQuery({ queryKey: ['schedule'], queryFn: listSchedule, staleTime: 5 * 60_000 });

  const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  const DAY_LABELS: Record<DayOfWeek, string> = {
    MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
    THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday', SUN: 'Sunday',
  };
  const TODAY: DayOfWeek = DAYS[(new Date().getDay() + 6) % 7]; // JS getDay(): Sun=0 -> our MON..SUN order

  // Mirrors the backend's own default (services/attendance_calendar.py::
  // _school_days_set) so an unconfigured school shows the right state
  // before anyone has ever saved anything.
  const DEFAULT_OPEN: Set<DayOfWeek> = new Set(['MON', 'TUE', 'WED', 'THU', 'FRI']);

  const scheduleMap = $derived(new Map<DayOfWeek, ScheduleDay>(($schedQ.data ?? []).map(s => [s.day_of_week, s])));
  function isOpen(day: DayOfWeek): boolean {
    return scheduleMap.get(day)?.is_school_day ?? DEFAULT_OPEN.has(day);
  }

  // One day selector drives both the open/closed toggle below and the bell
  // periods for that same day (PeriodsSection) — previously these were two
  // separate, visually-duplicate MON..SUN pickers stacked on one page.
  let selectedDay = $state<DayOfWeek>(TODAY);
  const selectedOpen = $derived(isOpen(selectedDay));

  let toggling = $state(false);
  const toggleMut = createMutation({
    mutationFn: (open: boolean) => upsertSchedule({ day_of_week: selectedDay, is_school_day: open }),
    onSuccess: (_, open) => {
      qc.invalidateQueries({ queryKey: ['schedule'] });
      toggling = false;
      toast.success(`${DAY_LABELS[selectedDay]} ${open ? 'opened' : 'closed'}.`);
    },
    onError: () => {
      toggling = false;
      toast.error(`Could not update ${DAY_LABELS[selectedDay]}.`);
    },
  });
  function toggleSelected() {
    toggling = true;
    $toggleMut.mutate(!selectedOpen);
  }

  // ── Period-level attendance opt-in (school-wide) ─────────────────────────
  const schoolQ = createQuery({ queryKey: ['my-school'], queryFn: getMySchool, staleTime: 60_000 });
  const periodAttendanceOn = $derived($schoolQ.data?.has_period_attendance ?? false);
  const periodAttendanceMut = createMutation({
    mutationFn: (enabled: boolean) => updateMySchool({ has_period_attendance: enabled }),
    onSuccess: (_, enabled) => {
      qc.invalidateQueries({ queryKey: ['my-school'] });
      toast.success(`Period-level attendance ${enabled ? 'enabled' : 'disabled'}.`);
    },
    onError: () => toast.error('Could not update this setting.'),
  });
</script>

{#if !canManage}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
    Only administrators can manage the school schedule.
  </div>
{:else}
  <p class="mb-3 text-sm text-[var(--fg-muted)]">
    Pick a day to open/close it for attendance and calendar generation, and manage its bell periods.
  </p>

  <!-- Day tabs — select, not toggle. Open/closed state shown via fill color;
       "today" shown via a ring (not a colored badge — amber is this app's
       "needs attention" color elsewhere, so a same-colored dot here would
       misread as a warning rather than a neutral "this is today" marker);
       the explicit open/closed toggle for the selected day lives in the
       status bar below. -->
  <div class="flex flex-wrap gap-2">
    {#each DAYS as day}
      {@const open = isOpen(day)}
      <button onclick={() => selectedDay = day}
        aria-label={DAY_LABELS[day]} title={DAY_LABELS[day]}
        class="flex min-h-[44px] min-w-[4.75rem] items-center justify-center rounded-xl border-2 px-3 text-sm font-semibold transition
          {selectedDay === day ? 'border-[var(--brand)]' : 'border-transparent'}
          {day === TODAY ? 'ring-2 ring-offset-2 ring-[var(--brand)] ring-offset-[var(--bg)]' : ''}
          {open ? 'bg-[var(--brand)] text-white' : 'border-[var(--border)] bg-[var(--card)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
        {DAY_LABELS[day].slice(0, 3)}
      </button>
    {/each}
  </div>

  <!-- Status bar for the selected day -->
  <div class="mt-3 flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
    <div class="flex items-center gap-2">
      <span class="h-2 w-2 shrink-0 rounded-full {selectedOpen ? 'bg-emerald-500' : 'bg-[var(--fg-subtle)]'}"></span>
      <p class="text-sm text-[var(--fg)]">
        <strong class="font-semibold">{DAY_LABELS[selectedDay]}</strong> is {selectedOpen ? 'open' : 'closed'}
      </p>
    </div>
    <button onclick={toggleSelected} disabled={toggling}
      class="min-h-[44px] shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
      {toggling ? '…' : selectedOpen ? 'Close this day' : 'Open this day'}
    </button>
  </div>

  <!-- Period-level attendance is additive to the always-available daily
       roll call — this is purely an opt-in for schools that want the
       richer per-lesson detail; leaving it off changes nothing. -->
  <div class="mt-3 flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
    <div class="min-w-0">
      <p class="text-sm font-medium text-[var(--fg)]">Period-level attendance marking</p>
      <p class="text-xs text-[var(--fg-muted)]">Optional — lets a subject teacher additionally mark attendance for their own lesson, on top of the daily roll call.</p>
    </div>
    <label class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center">
      <input type="checkbox" class="peer sr-only" checked={periodAttendanceOn}
        onchange={e => $periodAttendanceMut.mutate(e.currentTarget.checked)}
        disabled={$periodAttendanceMut.isPending} />
      <span class="h-6 w-11 rounded-full bg-[var(--hover)] transition peer-checked:bg-[var(--brand)]"></span>
      <span class="absolute left-1 h-4 w-4 rounded-full bg-white transition peer-checked:translate-x-5"></span>
    </label>
  </div>

  <PeriodsSection bind:selectedDay />
{/if}

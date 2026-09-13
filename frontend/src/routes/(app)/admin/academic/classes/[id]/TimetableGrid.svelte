<script lang="ts">
  import type { SchoolPeriod } from '$lib/api/schoolPeriods';
  import type { TimetableSlot } from '$lib/api/timetable';
  import type { DayOfWeek } from '$lib/api/attendance';

  interface Props {
    periods: SchoolPeriod[];
    slots: TimetableSlot[];
    classActive: boolean;
    onCellClick: (period: SchoolPeriod) => void;
    onExtend: (period: SchoolPeriod, subjectId: string) => void;
  }
  const { periods, slots, classActive, onCellClick, onExtend }: Props = $props();

  const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  const DAY_LABELS: Record<DayOfWeek, string> = {
    MON: 'Mon', TUE: 'Tue', WED: 'Wed', THU: 'Thu', FRI: 'Fri', SAT: 'Sat', SUN: 'Sun',
  };

  // Periods are defined per-day (a given period_number can have different
  // times, or not exist at all, on different days — e.g. a shorter Friday,
  // no Saturday periods) — so rows are the distinct period_numbers seen
  // anywhere, and each cell independently looks up its own day's period.
  const periodNumbers = $derived(
    [...new Set(periods.map(p => p.period_number))].sort((a, b) => a - b)
  );
  const periodByDayNumber = $derived(
    new Map(periods.map(p => [`${p.day_of_week}:${p.period_number}`, p]))
  );
  const rowLabel = $derived(
    new Map(periodNumbers.map(n => [n, periods.find(p => p.period_number === n)?.name ?? `Period ${n}`]))
  );
  const slotByPeriodId = $derived(new Map(slots.map(s => [s.period_id, s])));
</script>

{#if periodNumbers.length === 0}
  <p class="p-6 text-center text-sm text-[var(--fg-muted)]">
    No bell periods defined yet — set them up on the
    <a href="/attendance/schedule" class="underline" style="color:var(--brand)">Attendance Schedule</a> page.
  </p>
{:else}
  <div class="overflow-x-auto rounded-2xl border border-[var(--border)]">
    <table class="w-full border-collapse text-xs">
      <thead>
        <tr>
          <th class="sticky left-0 z-10 min-w-[88px] border-b border-r border-[var(--border)] bg-[var(--card)] p-2 text-left font-semibold text-[var(--fg-muted)]">
            Period
          </th>
          {#each DAYS as day}
            <th class="min-w-[130px] border-b border-[var(--border)] bg-[var(--card)] p-2 text-left font-semibold text-[var(--fg-muted)]">
              {DAY_LABELS[day]}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each periodNumbers as num (num)}
          <tr class="border-b border-[var(--border)] last:border-b-0">
            <td class="sticky left-0 z-10 border-r border-[var(--border)] bg-[var(--card)] p-2 align-top font-semibold text-[var(--fg)]">
              {rowLabel.get(num)}
            </td>
            {#each DAYS as day}
              {@const period = periodByDayNumber.get(`${day}:${num}`)}
              {@const slot = period ? slotByPeriodId.get(period.id) : undefined}
              {@const nextPeriod = periodByDayNumber.get(`${day}:${num + 1}`)}
              {@const nextSlot = nextPeriod ? slotByPeriodId.get(nextPeriod.id) : undefined}
              {@const canExtend = !!slot && !!slot.teacher_name && !!nextPeriod && !nextSlot && classActive}
              <td class="min-w-[130px] p-1 align-top">
                {#if !period}
                  <div class="h-14 rounded-lg bg-[var(--hover)]/30"></div>
                {:else}
                  <div class="relative">
                    <button
                      type="button"
                      disabled={!classActive}
                      onclick={() => onCellClick(period)}
                      class="flex h-14 w-full flex-col justify-center rounded-lg border px-2 py-1 text-left transition disabled:cursor-not-allowed
                        {slot
                          ? 'border-[var(--border)] bg-[var(--bg)] hover:border-[var(--brand)]'
                          : 'border-dashed border-[var(--border)] text-[var(--fg-subtle)] hover:bg-[var(--hover)]'}"
                    >
                      <p class="text-[9px] text-[var(--fg-subtle)]">{period.start_time.slice(0,5)}–{period.end_time.slice(0,5)}</p>
                      {#if slot}
                        <p class="truncate text-xs font-medium text-[var(--fg)]">{slot.subject_name}</p>
                        <p class="truncate text-[10px] text-[var(--fg-muted)]">{slot.teacher_name ?? 'No teacher assigned'}</p>
                      {:else}
                        <p class="text-xs">{classActive ? '+ Add' : 'Not assigned'}</p>
                      {/if}
                    </button>
                    {#if canExtend}
                      <button
                        type="button"
                        title="Extend {slot!.subject_name} into the next period (a double period)"
                        onclick={(e) => { e.stopPropagation(); onExtend(nextPeriod!, slot!.subject_id); }}
                        class="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--card)] text-[10px] font-bold text-[var(--fg-muted)] shadow-sm transition hover:border-[var(--brand)] hover:text-[var(--brand)]"
                      >
                        →
                      </button>
                    {/if}
                  </div>
                {/if}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

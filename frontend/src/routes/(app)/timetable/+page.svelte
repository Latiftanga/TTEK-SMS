<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { getMySchedule, type ScheduleEntry } from '$lib/api/timetable';
  import type { DayOfWeek } from '$lib/api/attendance';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';

  setPageTitle('My Timetable');

  const scheduleQ = createQuery({ queryKey: ['my-schedule'], queryFn: () => getMySchedule(), staleTime: 60_000 });

  const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  const DAY_LABELS: Record<DayOfWeek, string> = {
    MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
    THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday', SUN: 'Sunday',
  };
  const TODAY_KEY = DAYS[(new Date().getDay() + 6) % 7]; // JS getDay(): Sun=0 -> our MON..SUN order

  const byDay = $derived.by(() => {
    const map = new Map<DayOfWeek, ScheduleEntry[]>();
    for (const e of $scheduleQ.data ?? []) {
      if (!map.has(e.day_of_week)) map.set(e.day_of_week, []);
      map.get(e.day_of_week)!.push(e);
    }
    return map;
  });
  const hasAnything = $derived(($scheduleQ.data ?? []).length > 0);
</script>

<PageHeader title="My Timetable" description="What you teach, every day of the week." />

{#if $scheduleQ.isPending}
  <div class="space-y-3">{#each [1,2,3] as _}<div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>
{:else if !hasAnything}
  <EmptyState
    title="No timetable yet"
    description="Once your school assigns you subjects on the class timetable, they'll show up here." />
{:else}
  <div class="space-y-4">
    {#each DAYS as day}
      {@const entries = byDay.get(day) ?? []}
      {#if entries.length > 0}
        <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]"
             class:ring-2={day === TODAY_KEY} style={day === TODAY_KEY ? '--tw-ring-color: var(--brand)' : ''}>
          <div class="flex items-center gap-2 border-b border-[var(--border)] px-4 py-2.5">
            <p class="text-sm font-semibold text-[var(--fg)]">{DAY_LABELS[day]}</p>
            {#if day === TODAY_KEY}
              <span class="rounded-full px-2 py-0.5 text-[10px] font-bold text-white" style="background:var(--brand)">Today</span>
            {/if}
          </div>
          <div class="divide-y divide-[var(--border)]">
            {#each entries as e (e.class_id + e.subject_id + e.start_time)}
              <div class="flex items-center gap-3 px-4 py-3">
                <div class="w-24 shrink-0 text-xs font-medium text-[var(--fg-muted)]">
                  {e.start_time.slice(0,5)}–{e.end_time.slice(0,5)}
                </div>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-medium text-[var(--fg)]">{e.subject_name}</p>
                  <p class="truncate text-xs text-[var(--fg-muted)]">{e.class_name}</p>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/each}
  </div>
{/if}

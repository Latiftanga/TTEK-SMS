<script lang="ts">
  // "What do I teach tomorrow?" — mirrors MySubjectsCard.svelte's list shape,
  // with a calm empty state for a genuine non-school day (holiday/weekend)
  // instead of an empty list that would read as "nothing to teach at all."
  import type { ScheduleEntry } from '$lib/api/timetable';

  interface Props { schedule: ScheduleEntry[]; isSchoolDay: boolean; }
  const { schedule, isSchoolDay }: Props = $props();

  const icon = `<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>`;
</script>

<div>
  <p class="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Tomorrow</p>
  <div class="overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)]"
       style="box-shadow: var(--shadow-sm);">
    {#if !isSchoolDay}
      <div class="flex items-center gap-3.5 px-4 py-3.5">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--hover)]">
          <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html icon}
          </svg>
        </div>
        <p class="text-[0.8125rem] text-[var(--fg-muted)]">No lessons — it's not a school day.</p>
      </div>
    {:else if schedule.length === 0}
      <div class="flex items-center gap-3.5 px-4 py-3.5">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--hover)]">
          <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html icon}
          </svg>
        </div>
        <p class="text-[0.8125rem] text-[var(--fg-muted)]">Nothing timetabled for you yet.</p>
      </div>
    {:else}
      <div class="divide-y divide-[var(--border)]">
        {#each schedule as e (e.class_id + e.subject_id + e.start_time)}
          <div class="flex items-center gap-3.5 px-4 py-3.5">
            <div class="w-16 shrink-0 text-[0.6875rem] font-semibold text-[var(--fg-muted)]">
              {e.start_time.slice(0,5)}
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-[0.8125rem] font-semibold text-[var(--fg)]">{e.subject_name}</p>
              <p class="text-[0.6875rem] text-[var(--fg-muted)]">{e.class_name}</p>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<script lang="ts">
  // Period-level sibling of AttendanceMarkingOverview.svelte — school-wide
  // "who's marked, who hasn't" for periods, additive to the whole-day
  // overview above it. Renders nothing at all when the school hasn't
  // opted into period-level attendance, or there's nothing timetabled for
  // this day — never an empty state implying the feature exists.
  import { reactiveQuery } from '$lib/query.svelte';
  import { getPeriodMarkingStatus } from '$lib/api/attendance';

  interface Props {
    calendarId: string;
    enabled: boolean;
    onSelect: (classId: string, periodId: string) => void;
  }
  const { calendarId, enabled, onSelect }: Props = $props();

  const statusQ = reactiveQuery(() => ({
    queryKey: ['period-marking-status', calendarId] as const,
    queryFn: () => getPeriodMarkingStatus(calendarId),
    enabled: enabled && !!calendarId,
    staleTime: 30_000,
  }));

  const rows = $derived($statusQ.data ?? []);
  const unmarkedCount = $derived(rows.filter(r => !r.marked).length);
</script>

{#if enabled && rows.length > 0}
  <div class="mt-6">
    <div class="mb-3 flex items-center justify-between gap-2">
      <p class="text-sm font-semibold text-[var(--fg)]">Period marking status</p>
      {#if unmarkedCount > 0}
        <span class="text-xs font-semibold text-amber-600 dark:text-amber-400">{unmarkedCount} not marked yet</span>
      {:else}
        <span class="text-xs font-semibold text-green-600 dark:text-green-400">All periods marked</span>
      {/if}
    </div>
    <div class="space-y-2">
      {#each rows as r (r.class_id + r.period_id)}
        <button type="button" onclick={() => onSelect(r.class_id, r.period_id)}
          class="block w-full text-left {r.marked
            ? 'rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 transition hover:opacity-90'
            : 'group rounded-xl border border-amber-200 bg-amber-50 p-3 transition hover:bg-amber-100 dark:border-amber-900 dark:bg-amber-950/30 dark:hover:bg-amber-950/50'}">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-[0.8125rem] font-medium text-[var(--fg)]">{r.subject_name} · {r.class_name}</p>
              <p class="text-[11px] text-[var(--fg-muted)]">
                {r.period_name} · {r.start_time.slice(0, 5)}–{r.end_time.slice(0, 5)}
                {r.teacher_name ? ` · ${r.teacher_name}` : ''}
              </p>
            </div>
            {#if r.marked}
              <span class="shrink-0 text-green-600 dark:text-green-400">✓</span>
            {:else}
              <span class="flex shrink-0 items-center gap-1 text-xs font-bold text-amber-600 dark:text-amber-400">
                Mark now
                <svg class="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                </svg>
              </span>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  </div>
{/if}

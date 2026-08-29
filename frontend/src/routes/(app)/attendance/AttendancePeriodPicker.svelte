<script lang="ts">
  import { reactiveQuery } from '$lib/query.svelte';
  import { getMarkablePeriods } from '$lib/api/attendance';

  interface Props {
    classId: string;
    calendarId: string;
    enabled: boolean;
    periodId: string | null;
    onSelect: (periodId: string | null) => void;
  }
  const { classId, calendarId, enabled, periodId, onSelect }: Props = $props();

  // Additive to the always-available "Whole day" option — renders nothing
  // at all when the school hasn't opted in, or this day has no markable
  // periods, so a school that never turns this on sees zero difference.
  const periodsQ = reactiveQuery(() => ({
    queryKey: ['markable-periods', classId, calendarId] as const,
    queryFn:  () => getMarkablePeriods(classId, calendarId),
    enabled:  enabled && !!classId && !!calendarId,
    staleTime: 30_000,
  }));

  const periods = $derived($periodsQ.data ?? []);
</script>

{#if enabled && periods.length > 0}
  <div class="mb-3 flex flex-wrap gap-2">
    <button onclick={() => onSelect(null)}
      class="flex min-h-[44px] items-center rounded-xl border-2 px-3 text-sm font-semibold transition
        {periodId === null ? 'border-[var(--brand)] bg-[var(--brand)] text-white' : 'border-transparent bg-[var(--card)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
      Whole day
    </button>
    {#each periods as p (p.period_id)}
      <button onclick={() => p.can_mark && onSelect(p.period_id)} disabled={!p.can_mark}
        title={p.can_mark ? undefined : "You don't teach this period"}
        class="flex min-h-[44px] items-center gap-1.5 rounded-xl border-2 px-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40
          {periodId === p.period_id ? 'border-[var(--brand)] bg-[var(--brand)] text-white' : 'border-transparent bg-[var(--card)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
        {p.subject_name}
        {#if p.already_marked}<span class="h-1.5 w-1.5 rounded-full {periodId === p.period_id ? 'bg-white' : 'bg-emerald-500'}" title="Already marked"></span>{/if}
      </button>
    {/each}
  </div>
{/if}

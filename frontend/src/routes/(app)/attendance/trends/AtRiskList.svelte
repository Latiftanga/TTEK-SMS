<script lang="ts">
  import { reactiveQuery } from '$lib/query.svelte';
  import { getAtRiskStudents, type RiskTier } from '$lib/api/attendance';

  interface Props { termId: string; }
  const { termId }: Props = $props();

  const riskQ = reactiveQuery(() => ({
    queryKey: ['attendance-at-risk', termId] as const,
    queryFn:  () => getAtRiskStudents(termId),
    enabled:  !!termId,
    staleTime: 60_000,
  }));

  const students = $derived($riskQ.data ?? []);

  const TIER_STYLE: Record<RiskTier, string> = {
    WATCH:   'border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30',
    AT_RISK: 'border-orange-300 bg-orange-50 dark:border-orange-900 dark:bg-orange-950/30',
    SEVERE:  'border-red-300 bg-red-50 dark:border-red-900 dark:bg-red-950/30',
  };
  const TIER_LABEL: Record<RiskTier, string> = { WATCH: 'Watch', AT_RISK: 'At risk', SEVERE: 'Severe' };
  const TIER_TEXT: Record<RiskTier, string> = {
    WATCH:   'text-amber-700 dark:text-amber-400',
    AT_RISK: 'text-orange-700 dark:text-orange-400',
    SEVERE:  'text-red-700 dark:text-red-400',
  };
</script>

{#if $riskQ.isPending}
  <div class="space-y-2">{#each [1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if students.length === 0}
  <p class="rounded-xl border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--fg-muted)]">
    No students currently at risk — attendance is healthy across the term so far.
  </p>
{:else}
  <div class="space-y-2">
    {#each students as s (s.student_id)}
      <div class="flex items-center justify-between gap-3 rounded-xl border p-3 {TIER_STYLE[s.tier]}">
        <div class="min-w-0">
          <p class="truncate text-sm font-medium text-[var(--fg)]">{s.name}</p>
          <p class="text-xs text-[var(--fg-muted)]">{s.class_name ?? '—'} · {s.present}/{s.total} days present</p>
        </div>
        <div class="shrink-0 text-right">
          <p class="text-sm font-bold {TIER_TEXT[s.tier]}">{s.rate}%</p>
          <p class="text-[10px] font-semibold uppercase tracking-wide {TIER_TEXT[s.tier]}">{TIER_LABEL[s.tier]}</p>
        </div>
      </div>
    {/each}
  </div>
{/if}

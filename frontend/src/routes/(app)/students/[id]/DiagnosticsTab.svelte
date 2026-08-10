<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { listDiagnosticRecords } from '$lib/api/reports';

  interface Props { studentId: string; }
  const { studentId }: Props = $props();

  // Full lifetime history, no term filter — diagnostics have no fixed
  // schedule, unlike Behaviour/Fees which are naturally term-scoped.
  const recordsQ = createQuery({
    queryKey: ['diagnostic-records', studentId],
    queryFn:  () => listDiagnosticRecords(studentId),
    staleTime: 30_000,
  });
</script>

<div class="mb-4">
  <p class="text-sm text-[var(--fg-muted)]">
    A record of diagnostic assessments — used to identify a learning gap or guide a decision like
    placement, never part of the term report card. Recorded through the normal Assessments flow.
  </p>
</div>

{#if $recordsQ.isPending}
  <div class="space-y-2">{#each [1,2,3] as _}<div class="h-16 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
{:else if ($recordsQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No diagnostic assessments recorded for this student.</p>
  </div>
{:else}
  <div class="space-y-2">
    {#each $recordsQ.data ?? [] as r (r.id)}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-[var(--fg)]">{r.assessment_name}</span>
              <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-bold text-[var(--fg-muted)]">
                {r.subject_name}
              </span>
            </div>
            {#if r.notes}<p class="mt-1 text-sm text-[var(--fg-muted)]">{r.notes}</p>{/if}
            <p class="mt-1 text-xs text-[var(--fg-subtle)]">{r.recorded_date}</p>
          </div>
          <span class="shrink-0 font-mono text-sm font-semibold text-[var(--fg)]">
            {r.raw_score}<span class="text-[var(--fg-subtle)]">/{r.max_score}</span>
          </span>
        </div>
      </div>
    {/each}
  </div>
{/if}

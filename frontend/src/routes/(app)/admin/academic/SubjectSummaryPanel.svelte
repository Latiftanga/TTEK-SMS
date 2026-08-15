<script lang="ts">
  import { reactiveQuery } from '$lib/query.svelte';
  import { getSubjectSummary, type SubjectSummary } from '$lib/api/academic';

  interface Props { subjectId: string; termId: string; }
  const { subjectId, termId }: Props = $props();

  const summaryQ = reactiveQuery<SubjectSummary>(() => ({
    queryKey: ['subject-summary', subjectId, termId] as const,
    queryFn:  () => getSubjectSummary(subjectId, termId),
    enabled:  !!termId,
    staleTime: 30_000,
  }));
</script>

<div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 py-3 space-y-2.5">
  {#if !termId}
    <p class="text-xs text-[var(--fg-muted)]">No academic term selected.</p>
  {:else if $summaryQ.isPending}
    <div class="h-6 animate-pulse rounded-lg bg-[var(--hover)]"></div>
  {:else if $summaryQ.data}
    {@const s = $summaryQ.data}
    {#if s.total_classes === 0}
      <p class="text-xs text-[var(--fg-muted)]">Not assigned to any class yet.</p>
    {:else}
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="font-semibold text-[var(--fg)]">{s.total_students_registered} student{s.total_students_registered !== 1 ? 's' : ''}</span>
        <span class="text-[var(--fg-subtle)]">·</span>
        <span class="text-[var(--fg-muted)]">{s.total_classes} class{s.total_classes !== 1 ? 'es' : ''}</span>
        {#if s.classes_without_teacher > 0}
          <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
            ⚠ {s.classes_without_teacher} without a teacher
          </span>
        {/if}
      </div>
      <div class="divide-y divide-[var(--border)] overflow-hidden rounded-lg border border-[var(--border)]">
        {#each s.classes as c (c.class_id)}
          <div class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
            <span class="truncate font-medium text-[var(--fg)]">{c.display_name}</span>
            <span class="flex shrink-0 items-center gap-2">
              {#if c.teacher_name}
                <span class="text-xs text-[var(--fg-muted)]">{c.teacher_name}</span>
              {:else}
                <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">No teacher</span>
              {/if}
              <span class="font-mono text-xs text-[var(--fg-subtle)]">{c.registered_count} registered</span>
              <a href="/admin/academic/classes/{c.class_id}?tab=subjects"
                class="text-xs font-medium underline transition hover:text-[var(--fg)]" style="color:var(--brand)">Open class →</a>
            </span>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

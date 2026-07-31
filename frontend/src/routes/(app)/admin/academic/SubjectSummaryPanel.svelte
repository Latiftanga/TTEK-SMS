<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { getCurrentYear, getSubjectSummary } from '$lib/api/academic';

  interface Props { subjectId: string; }
  const { subjectId }: Props = $props();

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const termId = $derived(($yearQ.data?.terms ?? []).find(t => t.is_current)?.id ?? '');

  // Writable store pattern — keeps queryFn/enabled reactive to termId (which
  // starts empty until getCurrentYear resolves), mirroring
  // classes/[id]/SubjectRosterPanel.svelte's rosterOpts.
  const summaryOpts = writable({
    queryKey: ['subject-summary', subjectId, ''],
    queryFn: () => getSubjectSummary(subjectId, ''),
    enabled: false,
    staleTime: 30_000,
  });
  $effect(() => {
    const t = termId;
    summaryOpts.set({
      queryKey: ['subject-summary', subjectId, t],
      queryFn: () => getSubjectSummary(subjectId, t),
      enabled: !!t,
      staleTime: 30_000,
    });
  });
  const summaryQ = createQuery(summaryOpts);
</script>

<div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 py-3 space-y-2.5">
  {#if !termId}
    <p class="text-xs text-[var(--fg-muted)]">No current academic term.</p>
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
          <a href="/admin/academic/classes/{c.class_id}?tab=subjects"
            class="flex items-center justify-between gap-3 px-3 py-2 text-sm transition hover:bg-[var(--hover)]">
            <span class="truncate font-medium text-[var(--fg)]">{c.display_name}</span>
            <span class="flex shrink-0 items-center gap-2">
              {#if c.teacher_name}
                <span class="text-xs text-[var(--fg-muted)]">{c.teacher_name}</span>
              {:else}
                <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">No teacher</span>
              {/if}
              <span class="font-mono text-xs text-[var(--fg-subtle)]">{c.registered_count} registered</span>
            </span>
          </a>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { getCurrentYear, getProgrammeSummary } from '$lib/api/academic';

  interface Props { programmeId: string; }
  const { programmeId }: Props = $props();

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const yearId = $derived($yearQ.data?.id ?? '');

  // Writable store pattern — keeps queryFn/enabled reactive to yearId (which
  // starts empty until getCurrentYear resolves), mirroring
  // SubjectSummaryPanel.svelte's summaryOpts.
  const summaryOpts = writable({
    queryKey: ['programme-summary', programmeId, ''],
    queryFn: () => getProgrammeSummary(programmeId, ''),
    enabled: false,
    staleTime: 30_000,
  });
  $effect(() => {
    const y = yearId;
    summaryOpts.set({
      queryKey: ['programme-summary', programmeId, y],
      queryFn: () => getProgrammeSummary(programmeId, y),
      enabled: !!y,
      staleTime: 30_000,
    });
  });
  const summaryQ = createQuery(summaryOpts);
</script>

<div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 py-3 space-y-2.5">
  {#if !yearId}
    <p class="text-xs text-[var(--fg-muted)]">No current academic year.</p>
  {:else if $summaryQ.isPending}
    <div class="h-6 animate-pulse rounded-lg bg-[var(--hover)]"></div>
  {:else if $summaryQ.data}
    {@const s = $summaryQ.data}
    {#if s.total_classes === 0}
      <p class="text-xs text-[var(--fg-muted)]">Not assigned to any class yet.</p>
    {:else}
      <div class="flex flex-wrap items-center gap-2 text-xs">
        <span class="font-semibold text-[var(--fg)]">{s.total_students} student{s.total_students !== 1 ? 's' : ''}</span>
        <span class="text-[var(--fg-subtle)]">·</span>
        <span class="text-[var(--fg-muted)]">{s.total_classes} class{s.total_classes !== 1 ? 'es' : ''}</span>
      </div>
      <div class="divide-y divide-[var(--border)] overflow-hidden rounded-lg border border-[var(--border)]">
        {#each s.classes as c (c.class_id)}
          <a href="/admin/academic/classes/{c.class_id}?tab=students"
            class="flex items-center justify-between gap-3 px-3 py-2 text-sm transition hover:bg-[var(--hover)]">
            <span class="truncate font-medium text-[var(--fg)]">{c.display_name}</span>
            <span class="font-mono text-xs text-[var(--fg-subtle)]">{c.student_count} student{c.student_count !== 1 ? 's' : ''}</span>
          </a>
        {/each}
      </div>
    {/if}
  {/if}
</div>

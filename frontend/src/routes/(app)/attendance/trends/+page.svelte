<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listYears } from '$lib/api/academic';
  import { flattenTerms, resolveDefaultTerm, sortTermsDesc } from '$lib/academicPeriod';
  import { listMyAttendanceClasses, getAttendanceTrend, getAttendanceExportBlob } from '$lib/api/attendance';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import ActionMenu from '$lib/components/ActionMenu.svelte';
  import AttendanceTrendChart from './AttendanceTrendChart.svelte';
  import AtRiskList from './AtRiskList.svelte';

  const EXPORT_ICON = '<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>';

  setPageTitle('Attendance Trends');

  const yearsQ = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const allTerms = $derived(sortTermsDesc(flattenTerms($yearsQ.data ?? []).map(t => ({ ...t, yearName: '' }))));

  let termId = $state('');
  $effect(() => {
    if (!termId && allTerms.length > 0) termId = resolveDefaultTerm(allTerms)?.id ?? allTerms[0].id;
  });

  let classId = $state('');
  const classesQ = reactiveQuery(() => ({
    queryKey: ['my-attendance-classes', termId] as const,
    queryFn:  () => listMyAttendanceClasses(termId),
    enabled:  !!termId,
    staleTime: 5 * 60_000,
  }));

  const trendQ = reactiveQuery(() => ({
    queryKey: ['attendance-trend', termId, classId || 'all'] as const,
    queryFn:  () => getAttendanceTrend(termId, classId || undefined),
    enabled:  !!termId,
    staleTime: 60_000,
  }));

  let exporting = $state(false);
  async function exportAs(fmt: 'csv' | 'excel' | 'pdf') {
    if (!termId || exporting) return;
    exporting = true;
    try {
      const blob = await getAttendanceExportBlob(termId, fmt, classId || undefined);
      const ext = fmt === 'excel' ? 'xlsx' : fmt;
      const url = URL.createObjectURL(blob);
      Object.assign(document.createElement('a'), { href: url, download: `attendance.${ext}` }).click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Export failed.');
    } finally {
      exporting = false;
    }
  }
</script>

<div class="space-y-6">
  <!-- Selectors -->
  <div class="flex flex-wrap items-center gap-3">
    <select bind:value={termId}
      class="min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
      {#each allTerms as t (t.id)}
        <option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>
      {/each}
    </select>
    <select bind:value={classId}
      class="min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
      <option value="">All classes</option>
      {#each $classesQ.data ?? [] as c (c.id)}
        <option value={c.id}>{c.display_name}</option>
      {/each}
    </select>
    <div class="ml-auto">
      <ActionMenu actions={[
        { label: 'Export CSV',   icon: EXPORT_ICON, onClick: () => exportAs('csv') },
        { label: 'Export Excel', icon: EXPORT_ICON, onClick: () => exportAs('excel') },
        { label: 'Export PDF',   icon: EXPORT_ICON, onClick: () => exportAs('pdf') },
      ]} />
    </div>
  </div>

  <!-- Trend chart -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <h2 class="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Attendance rate over time</h2>
    {#if $trendQ.isPending}
      <div class="h-[180px] animate-pulse rounded-xl bg-[var(--hover)]"></div>
    {:else}
      <AttendanceTrendChart points={$trendQ.data ?? []} />
    {/if}
  </div>

  <!-- At-risk students -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <h2 class="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Chronic-absenteeism early warning</h2>
    {#if termId}
      <AtRiskList {termId} />
    {/if}
  </div>
</div>

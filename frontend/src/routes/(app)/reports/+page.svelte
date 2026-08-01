<script lang="ts">
  import { createQuery, createMutation } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listYears } from '$lib/api/academic';
  import {
    listClassEnrollments, getReportCardBlob, queueBulkReport, downloadBulkReport, listMyReportClasses,
    type EnrollmentForReport, type ReportFormat,
  } from '$lib/api/reports';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  setPageTitle('Report Cards');

  // ── Selectors ─────────────────────────────────────────────────────────────────
  let classId  = $state('');
  let termId   = $state('');
  let format   = $state<ReportFormat>('BASIC');

  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });

  const allTerms = $derived(
    ($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name })))
  );

  $effect(() => {
    const cur = allTerms.find(t => t.is_current);
    if (cur && !termId) termId = cur.id;
  });

  // Scoped to the caller's own ClassTeacher assignment(s) unless they hold
  // assessments.approve_scores — the backend decides, this page just renders
  // whatever it gets back, same for every role.
  const classesQ = reactiveQuery(() => ({
    queryKey: ['my-report-classes', termId] as const,
    queryFn:  () => listMyReportClasses(termId),
    enabled:  !!termId,
    staleTime: 5 * 60_000,
  }));

  const canApprove = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Enrollment list ───────────────────────────────────────────────────────────
  const enrollQ = reactiveQuery(() => ({
    queryKey: ['report-enrollments', classId, termId] as const,
    queryFn:  () => listClassEnrollments(classId, termId),
    enabled:  !!(classId && termId),
    staleTime: 60_000,
  }));
  const students = $derived<EnrollmentForReport[]>($enrollQ.data ?? []);

  // ── Per-student PDF ───────────────────────────────────────────────────────────
  let generating = $state<Set<string>>(new Set());

  async function openPDF(enroll: EnrollmentForReport) {
    if (generating.has(enroll.enrollment_id)) return;
    generating = new Set([...generating, enroll.enrollment_id]);
    try {
      const blob = await getReportCardBlob(enroll.enrollment_id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${enroll.admission_number}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch {
      toast.error(`Could not generate report card for ${enroll.display_name}.`);
    } finally {
      generating = new Set([...generating].filter(id => id !== enroll.enrollment_id));
    }
  }

  // ── Bulk generation ───────────────────────────────────────────────────────────
  let bulkJobId   = $state<string | null>(null);
  let bulkStatus  = $state<'idle' | 'queued' | 'polling' | 'ready' | 'error'>('idle');
  let pollTimer   = $state<ReturnType<typeof setTimeout> | null>(null);

  const POLL_INTERVAL_MS = 5000;
  const MAX_POLL_ATTEMPTS = 60; // ~5 minutes — a large class's worth of PDFs can take a while

  const bulkMut = createMutation({
    mutationFn: () => queueBulkReport(classId, termId, format),
    onSuccess: (job) => {
      bulkJobId  = job.job_id;
      bulkStatus = 'queued';
      toast.success('Bulk generation queued. Checking for completion…');
      pollForZip(job.job_id);
    },
    onError: () => { bulkStatus = 'error'; toast.error('Failed to queue bulk generation.'); },
  });

  function pollForZip(jobId: string) {
    bulkStatus = 'polling';
    let attempts = 0;
    const attempt = async () => {
      attempts += 1;
      try {
        const blob = await downloadBulkReport(jobId);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reports_${jobId}.zip`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
        bulkStatus = 'ready';
        bulkJobId  = null;
      } catch (e: unknown) {
        const status = (e as { response?: { status?: number } })?.response?.status;
        if (status !== 404) {
          // Not "still processing" — a real failure. Stop and let the user retry.
          bulkStatus = 'error';
          bulkJobId  = null;
          toast.error('Bulk generation failed. Try again.');
          return;
        }
        if (attempts >= MAX_POLL_ATTEMPTS) {
          bulkStatus = 'error';
          bulkJobId  = null;
          toast.error('Bulk generation is taking too long — it may have failed. Try again.');
          return;
        }
        pollTimer = setTimeout(attempt, POLL_INTERVAL_MS);
      }
    };
    attempt();
  }

  $effect(() => {
    return () => { if (pollTimer) clearTimeout(pollTimer); };
  });
</script>


<PageHeader title="Report Cards" description="Generate and download PDF report cards by class and term." />

<!-- Filters row -->
<div class="mb-5 flex flex-wrap items-end gap-3">
  <div class="flex-1 min-w-[150px]">
    <label for="rc-class" class="label">Class</label>
    <select id="rc-class" bind:value={classId} class="sel">
      <option value="">Select class…</option>
      {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
    </select>
  </div>

  <div class="flex-1 min-w-[180px]">
    <label for="rc-term" class="label">Term</label>
    <select id="rc-term" bind:value={termId} class="sel">
      <option value="">Select term…</option>
      {#each allTerms as t}<option value={t.id}>{t.yearName} — {t.name}</option>{/each}
    </select>
  </div>

  <div class="min-w-[130px]">
    <label for="rc-fmt" class="label">Format</label>
    <select id="rc-fmt" bind:value={format} class="sel">
      <option value="BASIC">Basic (GES)</option>
      <option value="SHS">SHS / WASSCE</option>
      <option value="ECM">Early Childhood</option>
    </select>
  </div>

  {#if canApprove && classId && termId && students.length > 0}
    <button
      onclick={() => $bulkMut.mutate()}
      disabled={$bulkMut.isPending || bulkStatus === 'polling' || bulkStatus === 'queued'}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white
             transition hover:opacity-90 disabled:opacity-50"
      style="background: var(--brand)">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>
      </svg>
      {#if bulkStatus === 'queued' || bulkStatus === 'polling'}
        Generating…
      {:else}
        Download all PDFs
      {/if}
    </button>
  {/if}
</div>

<!-- Prompt -->
{#if !classId || !termId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-12 text-center">
    <svg class="mx-auto mb-3 h-10 w-10 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
    </svg>
    <p class="text-sm font-medium text-[var(--fg-muted)]">Select a class and term to generate report cards.</p>
  </div>

<!-- Loading -->
{:else if $enrollQ.isPending}
  <div class="space-y-2">
    {#each [1,2,3,4,5] as _}
      <div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    {/each}
  </div>

<!-- Empty -->
{:else if students.length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-12 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No students enrolled in this class for the selected term.</p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Enrol students first via the Students module.</p>
  </div>

<!-- Student list -->
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <!-- Summary header -->
    <div class="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
      <p class="text-sm font-medium text-[var(--fg)]">
        {students.length} student{students.length === 1 ? '' : 's'}
        <span class="text-[var(--fg-muted)]">· {students[0]?.class_display_name ?? ''}</span>
      </p>
      <p class="text-xs text-[var(--fg-subtle)]">
        {format === 'BASIC' ? 'GES Basic format' : format === 'SHS' ? 'WASSCE SHS format' : 'Early Childhood format'}
      </p>
    </div>

    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Student</th>
          <th class="hidden px-4 py-3 sm:table-cell">Admission no.</th>
          <th class="hidden px-4 py-3 sm:table-cell">Gender</th>
          <th class="px-4 py-3 text-right">Report card</th>
        </tr>
      </thead>
      <tbody>
        {#each students as s (s.enrollment_id)}
          {@const busy = generating.has(s.enrollment_id)}
          <tr class="border-b border-[var(--border)] last:border-0 transition hover:bg-[var(--hover)]">
            <td class="px-4 py-3 font-medium text-[var(--fg)]">{s.display_name}</td>
            <td class="hidden px-4 py-3 font-mono text-xs text-[var(--fg-muted)] sm:table-cell">{s.admission_number}</td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">
              {s.gender === 'MALE' ? 'Male' : s.gender === 'FEMALE' ? 'Female' : '—'}
            </td>
            <td class="px-4 py-3 text-right">
              <button
                onclick={() => openPDF(s)}
                disabled={busy}
                class="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)]
                       px-3 py-1.5 text-xs font-semibold text-[var(--fg)] transition
                       hover:bg-[var(--hover)] disabled:opacity-50">
                {#if busy}
                  <svg class="h-3.5 w-3.5 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                  </svg>
                  Generating…
                {:else}
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>
                  </svg>
                  Download PDF
                {/if}
              </button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <p class="mt-3 text-xs text-[var(--fg-subtle)]">
    Report cards are generated on demand from live data. Published assessments with approved scores are included.
  </p>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

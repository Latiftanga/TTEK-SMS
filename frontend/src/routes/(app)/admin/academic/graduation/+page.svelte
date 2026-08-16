<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listYears, listClasses, type SchoolClass, type AcademicYear } from '$lib/api/academic';
  import { resolveDefaultYear, sortYearsDesc } from '$lib/academicPeriod';
  import { listStudents, bulkGraduate, type StudentSummary, type GraduationRecordCreate } from '$lib/api/students';
  import { setPageTitle } from '$lib/stores/title';
  import { toast } from '$lib/stores/toast';
  import { apiError } from '$lib/utils';
  import { portal } from '$lib/actions/portal';
  import PageHeader from '$lib/components/PageHeader.svelte';

  setPageTitle('Graduation');

  const qc = useQueryClient();

  const yearsQ  = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const classesQ = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 5 * 60_000 });

  let yearId   = $state('');
  let classId  = $state('');
  let deactivate = $state(true);
  let confirm  = $state(false);
  let result   = $state<{ processed: number; skipped: number } | null>(null);

  // resolveDefaultYear/sortYearsDesc, not $yearsQ.data[0] — API order isn't
  // guaranteed newest-first, unlike promote/+page.svelte's own sorted list.
  const years = $derived<AcademicYear[]>(sortYearsDesc($yearsQ.data ?? []));
  $effect(() => {
    if (!yearId && years.length) {
      yearId = resolveDefaultYear(years)?.id ?? '';
    }
  });

  const studentOpts = writable({ queryKey: ['grad-students', ''], queryFn: () => listStudents({}), enabled: false, staleTime: 60_000 });
  $effect(() => { if (classId) studentOpts.set({ queryKey: ['grad-students', classId], queryFn: () => listStudents({ class_id: classId, active_only: true }), enabled: true, staleTime: 60_000 }); });
  const studentsQ = createQuery(studentOpts);

  // Per-student action map: student_id → GraduationType | 'SKIP'
  type Action = 'SKIP' | 'GRADUATED' | 'WITHDRAWN' | 'TRANSFERRED';
  let actions  = $state<Record<string, Action>>({});
  let notes    = $state<Record<string, string>>({});

  // Reset when class changes
  $effect(() => { if (classId) { actions = {}; notes = {}; } });

  function setAll(action: Action) {
    const students: StudentSummary[] = $studentsQ.data ?? [];
    const next: Record<string, Action> = {};
    students.forEach(s => { next[s.id] = action; });
    actions = next;
  }

  const toProcess = $derived(
    ($studentsQ.data ?? []).filter(s => actions[s.id] && actions[s.id] !== 'SKIP')
  );

  const ACTION_LABELS: Record<Action, string> = {
    SKIP: 'Skip', GRADUATED: 'Graduate', WITHDRAWN: 'Withdraw', TRANSFERRED: 'Transfer',
  };
  const ACTION_COLORS: Record<Action, string> = {
    SKIP: 'text-[var(--fg-muted)]',
    GRADUATED: 'text-emerald-600 dark:text-emerald-400',
    WITHDRAWN: 'text-amber-600 dark:text-amber-400',
    TRANSFERRED: 'text-blue-600 dark:text-blue-400',
  };

  const gradMut = createMutation({
    mutationFn: () => {
      const records: GraduationRecordCreate[] = toProcess.map(s => ({
        student_id: s.id,
        graduation_type: actions[s.id] as Exclude<Action, 'SKIP'>,
        notes: notes[s.id] || null,
      }));
      return bulkGraduate({ academic_year_id: yearId, records, deactivate_students: deactivate });
    },
    onSuccess: (res) => {
      confirm = false;
      result = { processed: res.processed, skipped: res.skipped };
      qc.invalidateQueries({ queryKey: ['students'] });
      toast.success(`Done: ${res.processed} student(s) processed.`);
      actions = {}; notes = {};
    },
    onError: (e) => { confirm = false; toast.error(apiError(e, 'Could not process graduation.')); },
  });
</script>

<PageHeader
  title="Year-end Graduation"
  description="Record final outcomes for students completing or leaving the school at end of year."
/>

<div class="space-y-5">
  <!-- Year + Class selectors -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
    <label class="block">
      <span class="lx">Academic Year</span>
      <select bind:value={yearId} class="sel mt-1">
        {#each years as y}
          <option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>
        {/each}
      </select>
    </label>
    <label class="block">
      <span class="lx">Class</span>
      <select bind:value={classId} class="sel mt-1">
        <option value="">— select class —</option>
        {#each ($classesQ.data ?? []).sort((a, b) => a.display_name.localeCompare(b.display_name)) as c}
          <option value={c.id}>{c.display_name}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if classId}
    {#if $studentsQ.isPending}
      <div class="skeleton h-32 rounded-xl"></div>
    {:else if $studentsQ.data?.length === 0}
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-6 py-10 text-center text-sm text-[var(--fg-muted)]">
        No active students in this class.
      </div>
    {:else if $studentsQ.data}
      <!-- Bulk action bar -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs font-medium text-[var(--fg-muted)]">Set all to:</span>
        {#each (['GRADUATED', 'WITHDRAWN', 'TRANSFERRED', 'SKIP'] as Action[]) as a}
          <button onclick={() => setAll(a)}
            class="rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium
                   text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
            {ACTION_LABELS[a]}
          </button>
        {/each}
        {#if toProcess.length > 0}
          <span class="ml-auto text-xs font-medium" class:text-emerald-600={toProcess.length > 0}>
            {toProcess.length} student{toProcess.length !== 1 ? 's' : ''} will be processed
          </span>
        {/if}
      </div>

      <!-- Student list -->
      <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div class="divide-y divide-[var(--border)]">
          {#each $studentsQ.data as s (s.id)}
            {@const act = actions[s.id] ?? 'SKIP'}
            <div class="flex flex-wrap items-start gap-3 px-4 py-3">
              <!-- Name -->
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
                <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{s.admission_number}</p>
              </div>

              <!-- Action selector -->
              <select
                value={act}
                onchange={(e) => { actions[s.id] = (e.target as HTMLSelectElement).value as Action; }}
                class="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs
                       font-medium focus:border-[var(--brand)] focus:outline-none transition
                       {ACTION_COLORS[act]}">
                {#each (['SKIP', 'GRADUATED', 'WITHDRAWN', 'TRANSFERRED'] as Action[]) as a}
                  <option value={a}>{ACTION_LABELS[a]}</option>
                {/each}
              </select>

              <!-- Notes (only when non-skip) -->
              {#if act !== 'SKIP'}
                <input
                  bind:value={notes[s.id]}
                  placeholder="Notes (optional)"
                  class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)]
                         px-3 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                         focus:border-[var(--brand)] focus:outline-none transition" />
              {/if}
            </div>
          {/each}
        </div>
      </div>

      <!-- Options + Process button -->
      <div class="flex flex-wrap items-center justify-between gap-4">
        <label class="flex items-center gap-2 text-sm text-[var(--fg-muted)]">
          <input type="checkbox" bind:checked={deactivate}
            class="h-4 w-4 rounded border-[var(--border)] accent-[var(--brand)]" />
          Deactivate students after processing
        </label>

        <button
          onclick={() => confirm = true}
          disabled={toProcess.length === 0}
          class="rounded-xl px-6 py-2.5 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-40"
          style="background: var(--brand)">
          Review &amp; Confirm ({toProcess.length})
        </button>
      </div>
    {/if}
  {/if}

  {#if result}
    <div class="rounded-xl border border-emerald-200 dark:border-emerald-800
                bg-emerald-50 dark:bg-emerald-950/30 px-5 py-4 text-sm text-emerald-700 dark:text-emerald-300">
      Processed {result.processed} student{result.processed !== 1 ? 's' : ''}.
      {#if result.skipped > 0}
        {result.skipped} already had records and were skipped.
      {/if}
    </div>
  {/if}
</div>

<!-- Confirm dialog -->
{#if confirm}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="flex w-full max-w-sm flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl"
         style="max-height: 90vh">
      <div class="shrink-0 px-6 pt-6">
        <h2 class="mb-1 text-base font-semibold text-[var(--fg)]">Confirm graduation</h2>
        <p class="text-sm text-[var(--fg-muted)]">
          This will record outcomes for {toProcess.length} student{toProcess.length !== 1 ? 's' : ''}{deactivate ? ' and deactivate their accounts.' : '.'}
        </p>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <div class="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--bg)]">
          {#each toProcess.slice(0, 6) as s}
            <div class="flex items-center justify-between px-3 py-2 text-xs">
              <span class="font-medium text-[var(--fg)]">{s.display_name}</span>
              <span class="{ACTION_COLORS[actions[s.id] ?? 'SKIP']} font-semibold">
                {ACTION_LABELS[actions[s.id] ?? 'SKIP']}
              </span>
            </div>
          {/each}
          {#if toProcess.length > 6}
            <div class="px-3 py-2 text-xs text-[var(--fg-muted)]">
              …and {toProcess.length - 6} more
            </div>
          {/if}
        </div>
      </div>

      <div class="flex shrink-0 gap-3 border-t border-[var(--border)] px-6 py-4">
        <button onclick={() => confirm = false}
          class="flex-1 rounded-xl border border-[var(--border)] py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
        <button onclick={() => $gradMut.mutate()} disabled={$gradMut.isPending}
          class="flex-1 rounded-xl py-2 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$gradMut.isPending ? 'Processing…' : 'Process'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

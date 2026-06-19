<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listTermEnrollments, enrollStudent } from '$lib/api/students';
  import { listClasses, listYears, type AcademicTerm } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props { studentId: string; }
  const { studentId }: Props = $props();

  const qc = useQueryClient();

  const enrollmentsQ = createQuery({
    queryKey: ['student-enrollments', studentId],
    queryFn:  () => listTermEnrollments(studentId),
    staleTime: 60_000,
  });

  const classesQ = createQuery({
    queryKey: ['classes'],
    queryFn:  () => listClasses(),
    staleTime: 5 * 60_000,
  });

  const yearsQ = createQuery({
    queryKey: ['academic-years'],
    queryFn:  listYears,
    staleTime: 5 * 60_000,
  });

  const allTerms = $derived((): AcademicTerm[] =>
    ($yearsQ.data ?? []).flatMap(y => y.terms).sort((a, b) =>
      b.start_date.localeCompare(a.start_date)
    )
  );

  let showForm    = $state(false);
  let classId     = $state('');
  let termId      = $state('');
  let formError   = $state('');

  const enrollMut = createMutation({
    mutationFn: () => enrollStudent({ student_id: studentId, class_id: classId, academic_term_id: termId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-enrollments', studentId] });
      showForm = false; classId = ''; termId = ''; formError = '';
      toast.success('Student enrolled.');
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not enroll.';
    },
  });

  function handleEnroll() {
    formError = '';
    if (!classId) { formError = 'Select a class.'; return; }
    if (!termId)  { formError = 'Select a term.'; return; }
    $enrollMut.mutate();
  }

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { year: 'numeric', month: 'short', day: 'numeric' });
  }
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <p class="text-sm text-[var(--fg-muted)]">Class assignments per academic term.</p>
    <button onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90" style="background: var(--brand)">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Enroll in term
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 class="mb-3 text-sm font-semibold text-[var(--fg)]">New term enrollment</h3>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="et-class" class="label">Class <span class="text-red-500">*</span></label>
          <select id="et-class" bind:value={classId} class="input">
            <option value="">Select class…</option>
            {#each $classesQ.data ?? [] as c}
              <option value={c.id}>{c.display_name}</option>
            {/each}
          </select>
        </div>
        <div>
          <label for="et-term" class="label">Academic term <span class="text-red-500">*</span></label>
          <select id="et-term" bind:value={termId} class="input">
            <option value="">Select term…</option>
            {#each allTerms() as t}
              <option value={t.id}>{t.name}</option>
            {/each}
          </select>
        </div>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-3 flex gap-2">
        <button onclick={handleEnroll} disabled={$enrollMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
          {$enrollMut.isPending ? 'Enrolling…' : 'Enroll'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if $enrollmentsQ.isPending}
    <div class="space-y-2">{#each [1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($enrollmentsQ.data ?? []).length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No term enrollments yet. Enroll this student in a class above.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] bg-[var(--hover)]">
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Class</th>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)] hidden sm:table-cell">Enrolled</th>
            <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each $enrollmentsQ.data ?? [] as e (e.id)}
            <tr>
              <td class="px-4 py-3 font-medium text-[var(--fg)]">{e.class_display_name}</td>
              <td class="px-4 py-3 text-xs text-[var(--fg-muted)] hidden sm:table-cell">{fmtDate(e.created_at)}</td>
              <td class="px-4 py-3">
                {#if e.is_active}
                  <span class="rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Current</span>
                {:else}
                  <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--fg-muted)]">Past</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

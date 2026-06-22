<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listClassAssignments, assignStudentToClass,
    listTermEnrollments, enrollStudent,
  } from '$lib/api/students';
  import { listClasses, listYears } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';
  import TermRegistrationRow from './TermRegistrationRow.svelte';

  interface Props { studentId: string; }
  const { studentId }: Props = $props();

  const qc = useQueryClient();

  // ── Queries ───────────────────────────────────────────────────────────────────

  const assignmentsQ = createQuery({
    queryKey: ['student-class-assignments', studentId],
    queryFn:  () => listClassAssignments(studentId),
    staleTime: 60_000,
  });

  const termRegsQ = createQuery({
    queryKey: ['student-term-enrollments', studentId],
    queryFn:  () => listTermEnrollments(studentId),
    staleTime: 60_000,
  });

  const yearsQ = createQuery({
    queryKey: ['academic-years'],
    queryFn:  listYears,
    staleTime: 5 * 60_000,
  });

  // Declared before classesQ — used in its enabled callback (avoids TDZ)
  let showClassForm = $state(false);

  const classesQ = createQuery({
    queryKey: ['classes'],
    queryFn:  () => listClasses(),
    enabled:  () => showClassForm,
    staleTime: 5 * 60_000,
  });

  // ── Derived ───────────────────────────────────────────────────────────────────

  const yearMap = $derived(new Map(($yearsQ.data ?? []).map(y => [y.id, y])));

  // academic_term_id → TermEnrollmentRead
  const termRegMap = $derived(new Map(($termRegsQ.data ?? []).map(te => [te.academic_term_id, te])));

  // Most-recent year first
  const sortedAssignments = $derived(
    [...($assignmentsQ.data ?? [])].sort((a, b) => {
      const ya = yearMap.get(a.academic_year_id);
      const yb = yearMap.get(b.academic_year_id);
      return (yb?.start_date ?? '').localeCompare(ya?.start_date ?? '');
    })
  );

  // ── Collapsible class cards ───────────────────────────────────────────────────

  // Default: expand active assignment; collapse everything else
  let expandedIds = $state(new Set<string>());

  $effect(() => {
    if (($assignmentsQ.data ?? []).length > 0 && expandedIds.size === 0) {
      const active = ($assignmentsQ.data ?? []).find(a => a.is_active)
        ?? ($assignmentsQ.data ?? [])[0];
      if (active) expandedIds = new Set([active.id]);
    }
  });

  function toggleClass(id: string) {
    const s = new Set(expandedIds);
    s.has(id) ? s.delete(id) : s.add(id);
    expandedIds = s;
  }

  // ── Mutations ─────────────────────────────────────────────────────────────────

  let regError = $state('');

  const registerMut = createMutation({
    mutationFn: (termId: string) => enrollStudent({ student_id: studentId, academic_term_id: termId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-term-enrollments', studentId] });
      regError = '';
      toast.success('Registered for term.');
    },
    onError: (e: unknown) => {
      regError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not register for term.';
    },
  });

  let caYearId  = $state('');
  let caClassId = $state('');
  let caError   = $state('');

  const assignMut = createMutation({
    mutationFn: () => assignStudentToClass({
      student_id: studentId, class_id: caClassId, academic_year_id: caYearId,
    }),
    onSuccess: (newAssignment) => {
      qc.invalidateQueries({ queryKey: ['student-class-assignments', studentId] });
      expandedIds = new Set([newAssignment.id]);
      showClassForm = false; caYearId = ''; caClassId = ''; caError = '';
      toast.success('Class assigned.');
    },
    onError: (e: unknown) => {
      caError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not assign to class.';
    },
  });

  function handleAssign() {
    caError = '';
    if (!caYearId)  { caError = 'Select an academic year.'; return; }
    if (!caClassId) { caError = 'Select a class.'; return; }
    $assignMut.mutate();
  }
</script>

<!-- ── LOADING ────────────────────────────────────────────────────────────────── -->
{#if $assignmentsQ.isPending || $yearsQ.isPending}
  <div class="space-y-3">
    {#each [1, 2] as _}
      <div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    {/each}
  </div>

<!-- ── NO CLASS YET ───────────────────────────────────────────────────────────── -->
{:else if sortedAssignments.length === 0}
  <div class="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-800 dark:bg-amber-950/30">
    <p class="text-sm font-semibold text-amber-800 dark:text-amber-300">No class assigned</p>
    <p class="mt-1 text-xs text-amber-700 dark:text-amber-400">
      Assign this student to a class before registering them for a term.
    </p>
    {#if !showClassForm}
      <button onclick={() => showClassForm = true}
        class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        Assign to class
      </button>
    {:else}
      <div class="mt-4 border-t border-amber-200 pt-4 space-y-3 dark:border-amber-800">
        <div class="grid gap-2 sm:grid-cols-2">
          <select bind:value={caYearId} class="sel-amber">
            <option value="">Academic year…</option>
            {#each $yearsQ.data ?? [] as y}<option value={y.id}>{y.name}</option>{/each}
          </select>
          <select bind:value={caClassId} class="sel-amber">
            <option value="">Class…</option>
            {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
          </select>
        </div>
        {#if caError}<p class="text-xs text-red-600">{caError}</p>{/if}
        <div class="flex gap-2">
          <button onclick={handleAssign} disabled={$assignMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
            style="background: var(--brand)">
            {$assignMut.isPending ? 'Assigning…' : 'Assign'}
          </button>
          <button onclick={() => { showClassForm = false; caError = ''; }}
            class="text-sm text-amber-700 transition hover:text-amber-900">Cancel</button>
        </div>
      </div>
    {/if}
  </div>

<!-- ── COLLAPSIBLE CLASS → TERM → SUBJECT TREE ───────────────────────────────── -->
{:else}
  <div class="space-y-2">

    {#each sortedAssignments as assignment (assignment.id)}
      {@const year      = yearMap.get(assignment.academic_year_id)}
      {@const yearTerms = [...(year?.terms ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date))}
      {@const isOpen    = expandedIds.has(assignment.id)}

      <!-- ── Level 1: Class card ──────────────────────────────────────────────── -->
      <div class="overflow-hidden rounded-2xl border bg-[var(--card)] transition-all
        {isOpen ? 'border-[var(--brand)]/40' : 'border-[var(--border)]'}">

        <!-- Class header (clickable) -->
        <button
          onclick={() => toggleClass(assignment.id)}
          class="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform duration-200 {isOpen ? 'rotate-90' : ''}"
            fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
          </svg>
          <div class="flex min-w-0 flex-1 items-center gap-2.5">
            <span class="font-semibold text-[var(--fg)]">{assignment.class_display_name}</span>
            <span class="text-xs text-[var(--fg-muted)]">{year?.name ?? '—'}</span>
          </div>
          {#if assignment.is_active}
            <span class="shrink-0 flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
              Active
            </span>
          {/if}
        </button>

        <!-- ── Level 2 + 3: Terms + Subjects (when class expanded) ────────────── -->
        {#if isOpen}
          <div class="border-t border-[var(--border)] px-4 pb-3 pt-2">
            {#if yearTerms.length === 0}
              <p class="py-3 text-sm text-[var(--fg-muted)]">No terms configured for this academic year.</p>
            {:else}
              <!-- Left-border indent groups terms under this class visually -->
              <div class="border-l-2 border-[var(--border)] pl-3 space-y-0.5">
                {#each yearTerms as term}
                  {#if termRegMap.has(term.id)}
                    <!-- ── Registered term → expands inline for subjects ─────── -->
                    <TermRegistrationRow
                      enrollment={termRegMap.get(term.id)!}
                      termLabel={term.name}
                      inline={true}
                    />
                  {:else}
                    <!-- ── Not yet registered ────────────────────────────────── -->
                    <div class="flex items-center justify-between py-2 pl-1 pr-3">
                      <div class="flex items-center gap-2">
                        <div class="h-1.5 w-1.5 rounded-full bg-[var(--border)]"></div>
                        <span class="text-sm text-[var(--fg-muted)]">{term.name}</span>
                      </div>
                      <div class="flex flex-col items-end gap-0.5">
                        <button
                          onclick={() => { regError = ''; $registerMut.mutate(term.id); }}
                          disabled={$registerMut.isPending && $registerMut.variables === term.id}
                          class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
                          style="background: var(--brand)">
                          {$registerMut.isPending && $registerMut.variables === term.id ? 'Registering…' : 'Register'}
                        </button>
                        {#if regError && $registerMut.variables === term.id}
                          <p class="text-[10px] text-red-500">{regError}</p>
                        {/if}
                      </div>
                    </div>
                  {/if}
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}

    <!-- ── Assign to another year ────────────────────────────────────────────── -->
    {#if !showClassForm}
      <button
        onclick={() => { showClassForm = true; caError = ''; }}
        class="flex items-center gap-1.5 pt-1 text-xs font-semibold transition hover:underline"
        style="color: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Assign to class for another year
      </button>
    {:else}
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <p class="text-xs font-medium text-[var(--fg-muted)]">Assign to a class for a different academic year</p>
        <div class="grid gap-2 sm:grid-cols-2">
          <select bind:value={caYearId} class="sel">
            <option value="">Academic year…</option>
            {#each $yearsQ.data ?? [] as y}<option value={y.id}>{y.name}</option>{/each}
          </select>
          <select bind:value={caClassId} class="sel">
            <option value="">Class…</option>
            {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
          </select>
        </div>
        {#if caError}<p class="text-xs text-red-500">{caError}</p>{/if}
        <div class="flex gap-2">
          <button onclick={handleAssign} disabled={$assignMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
            style="background: var(--brand)">
            {$assignMut.isPending ? 'Assigning…' : 'Assign'}
          </button>
          <button onclick={() => { showClassForm = false; caError = ''; }}
            class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      </div>
    {/if}

  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel      { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .sel-amber { @apply w-full rounded-xl border border-amber-300 bg-white/60 px-3 py-2 text-sm text-amber-900 focus:border-amber-500 focus:outline-none transition dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100; }
</style>

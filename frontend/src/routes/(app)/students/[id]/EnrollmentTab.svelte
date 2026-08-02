<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listClassAssignments, assignStudentToClass,
    listTermEnrollments, enrollStudent,
  } from '$lib/api/students';
  import { listClasses, listYears, type SchoolClass, type AcademicYear } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';
  import TermTimelineRow from './TermTimelineRow.svelte';
  import ClassActionPanel   from './ClassActionPanel.svelte';

  interface Props { studentId: string; canEdit?: boolean; canManage?: boolean; }
  const { studentId, canEdit = true, canManage = true }: Props = $props();

  const qc = useQueryClient();

  // ── Queries ───────────────────────────────────────────────────────────────────
  const assignmentsQ = createQuery({ queryKey: ['student-class-assignments', studentId], queryFn: () => listClassAssignments(studentId), staleTime: 60_000 });
  const termRegsQ    = createQuery({ queryKey: ['student-term-enrollments', studentId],  queryFn: () => listTermEnrollments(studentId),  staleTime: 60_000 });
  const yearsQ       = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });
  const classesQ     = createQuery({ queryKey: ['classes'],        queryFn: listClasses, staleTime: 5 * 60_000 });

  // ── Derived ───────────────────────────────────────────────────────────────────
  const yearMap    = $derived(new Map(($yearsQ.data ?? []).map(y => [y.id, y])));
  const termRegMap = $derived(new Map(($termRegsQ.data ?? []).map(te => [te.academic_term_id, te])));
  const classes    = $derived<SchoolClass[]>($classesQ.data ?? []);
  const years      = $derived<AcademicYear[]>($yearsQ.data ?? []);

  const sortedAssignments = $derived(
    [...($assignmentsQ.data ?? [])].sort((a, b) => {
      const ya = yearMap.get(a.academic_year_id);
      const yb = yearMap.get(b.academic_year_id);
      return (yb?.start_date ?? '').localeCompare(ya?.start_date ?? '');
    })
  );

  const activeAssignment = $derived(sortedAssignments.find(a => a.is_active) ?? sortedAssignments[0] ?? null);
  const activeClass      = $derived(activeAssignment ? classes.find(c => c.id === activeAssignment.class_id) ?? null : null);

  // ── Term registration (shared across every "Not registered" row) ─────────────
  // A 422 here means the term's fee gate blocked this student (the other 422
  // case — no class assignment — can't happen from this button, since we're
  // already inside an assigned class's term list). Offer an inline waiver
  // input instead of just showing the error; the waive attempt is only
  // actually honoured server-side if the caller has fees.manage.
  let regError = $state('');
  let blocked = $state<{ termId: string; message: string } | null>(null);
  let waiverReason = $state('');
  let waiverError = $state('');

  const registerMut = createMutation({
    mutationFn: (termId: string) => enrollStudent({ student_id: studentId, academic_term_id: termId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-term-enrollments', studentId] });
      regError = ''; blocked = null; toast.success('Registered for term.');
    },
    onError: (e: unknown, termId) => {
      const err = e as { response?: { status?: number; data?: { detail?: string } } };
      const detail = err?.response?.data?.detail ?? 'Could not register.';
      if (err?.response?.status === 422) {
        blocked = { termId, message: detail }; waiverReason = ''; waiverError = '';
      } else {
        regError = detail;
      }
    },
  });

  const waiveMut = createMutation({
    mutationFn: (termId: string) => enrollStudent({ student_id: studentId, academic_term_id: termId, fee_waiver_reason: waiverReason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-term-enrollments', studentId] });
      blocked = null; waiverReason = ''; waiverError = '';
      toast.success('Registered for term — fee gate waived.');
    },
    onError: (e: unknown) => {
      waiverError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not push through — you may not have permission to waive the fee gate.';
    },
  });

  // ── First assignment (no history) ─────────────────────────────────────────────
  let showFirstForm = $state(false);
  let caYearId = $state('');
  let caClassId = $state('');
  let caError = $state('');

  const firstAssignMut = createMutation({
    mutationFn: () => assignStudentToClass({ student_id: studentId, class_id: caClassId, academic_year_id: caYearId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-class-assignments', studentId] });
      showFirstForm = false; caYearId = ''; caClassId = ''; caError = '';
      toast.success('Class assigned.');
    },
    onError: (e: unknown) => { caError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not assign.'; },
  });

  // ── Year-end actions — collapsed by default; routine registration above is the
  // common path, promote/repeat/demote/transfer is a rare, year-end-only action.
  let yearEndOpen = $state(false);
</script>

<!-- Loading -->
{#if $assignmentsQ.isPending || $yearsQ.isPending || $classesQ.isPending}
  <div class="space-y-3">{#each [1,2] as _}<div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>

<!-- No class yet -->
{:else if sortedAssignments.length === 0}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="text-sm font-semibold text-[var(--fg)]">No class assigned</p>
    <p class="mt-1 text-xs text-[var(--fg-muted)]">Assign this student to a class before registering them for a term.</p>
    {#if canEdit}
      {#if !showFirstForm}
        <button onclick={() => showFirstForm = true}
          class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background: var(--brand)">Assign to class</button>
      {:else}
        <div class="mt-4 space-y-3 border-t border-[var(--border)] pt-4">
          <div class="grid gap-2 sm:grid-cols-2">
            <select bind:value={caYearId} class="sel">
              <option value="">Academic year…</option>
              {#each years as y}<option value={y.id}>{y.name}</option>{/each}
            </select>
            <select bind:value={caClassId} class="sel">
              <option value="">Class…</option>
              {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
            </select>
          </div>
          {#if caError}<p class="text-xs text-red-600">{caError}</p>{/if}
          <div class="flex gap-2">
            <button onclick={() => { caError=''; if (!caYearId){caError='Select year.'; return;} if (!caClassId){caError='Select class.'; return;} $firstAssignMut.mutate(); }}
              disabled={$firstAssignMut.isPending}
              class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
              style="background: var(--brand)">{$firstAssignMut.isPending ? 'Assigning…' : 'Assign'}</button>
            <button onclick={() => { showFirstForm = false; caError = ''; }}
              class="text-sm text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
          </div>
        </div>
      {/if}
    {/if}
  </div>

<!-- Timeline: one row per term, across every year the student has been assigned a class in -->
{:else}
  <div class="space-y-4">
    {#each sortedAssignments as assignment (assignment.id)}
      {@const year      = yearMap.get(assignment.academic_year_id)}
      {@const yearTerms = [...(year?.terms ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date))}
      <div>
        <div class="mb-1.5 flex items-center gap-2 px-1">
          <p class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">{year?.name ?? '—'}</p>
          {#if year?.is_current}
            <span class="rounded-full bg-[var(--brand)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--brand)]">current</span>
          {/if}
        </div>
        {#if yearTerms.length === 0}
          <p class="px-1 text-sm text-[var(--fg-muted)]">No terms configured for this academic year.</p>
        {:else}
          <div class="space-y-1.5">
            {#each yearTerms as term (term.id)}
              <TermTimelineRow
                {term}
                classDisplayName={assignment.class_display_name}
                assignmentActive={assignment.is_active}
                enrollment={termRegMap.get(term.id) ?? null}
                isRegistering={$registerMut.isPending && $registerMut.variables === term.id}
                registerError={regError && $registerMut.variables === term.id ? regError : ''}
                isBlocked={blocked?.termId === term.id}
                blockedMessage={blocked?.termId === term.id ? blocked.message : ''}
                {waiverReason}
                waiverError={blocked?.termId === term.id ? waiverError : ''}
                onRegister={() => { regError = ''; $registerMut.mutate(term.id); }}
                onWaiverReasonChange={(v) => waiverReason = v}
                onWaive={() => { waiverError = ''; if (!waiverReason.trim()) { waiverError = 'Reason required.'; return; } $waiveMut.mutate(term.id); }}
                onCancelWaiver={() => blocked = null}
                {canEdit}
              />
            {/each}
          </div>
        {/if}
      </div>
    {/each}

    <!-- Year-end / transfer actions — collapsed by default; year-round students never need this -->
    {#if canEdit || canManage}
      {#if !yearEndOpen}
        <button onclick={() => yearEndOpen = true}
          class="flex w-full items-center justify-between rounded-2xl border border-dashed border-[var(--border)]
                 px-5 py-4 text-left transition hover:border-[var(--brand)]/40 hover:bg-[var(--brand)]/5">
          <div>
            <p class="text-sm font-semibold text-[var(--fg)]">Manage year-end status</p>
            <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Promote, repeat, demote, or transfer this student</p>
          </div>
          <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
          </svg>
        </button>
      {:else}
        <ClassActionPanel
          {studentId} {activeClass} {classes} {years}
          onDone={() => yearEndOpen = false}
          {canEdit} {canManage}
        />
      {/if}
    {/if}
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

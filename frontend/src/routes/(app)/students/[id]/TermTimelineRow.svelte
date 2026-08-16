<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { listSubjectRegistrations, type TermEnrollmentRead } from '$lib/api/students';
  import { type AcademicTerm } from '$lib/api/academic';
  import SubjectRegistrationPanel from './SubjectRegistrationPanel.svelte';

  interface Props {
    term: AcademicTerm;
    classDisplayName: string;
    assignmentActive: boolean;
    enrollment: TermEnrollmentRead | null;
    isRegistering?: boolean;
    registerError?: string;
    onRegister?: () => void;
    canEdit?: boolean;
  }
  const {
    term, classDisplayName, assignmentActive, enrollment,
    isRegistering = false, registerError = '',
    onRegister,
    canEdit = true,
  }: Props = $props();

  let expanded = $state(false);

  // An inactive TermEnrollment (student withdrew from this specific term) still
  // exists as a row but can't take subject registrations — register_subjects()
  // filters TermEnrollment.is_active server-side, so treat it like "not
  // registered" for that purpose. The Register button still works: creating a
  // term enrollment against an existing inactive row reactivates it in place
  // (services/student_enrollment.py::create_term_enrollment).
  const isRegistered = $derived(!!enrollment && enrollment.is_active);

  const subjectRegsQ = createQuery({
    queryKey: ['term-subject-regs', enrollment?.id ?? 'none'],
    queryFn:  () => listSubjectRegistrations(enrollment!.id),
    enabled:  isRegistered,
    staleTime: 60_000,
  });
  const subjectCount = $derived($subjectRegsQ.data?.length);
</script>

<div class="overflow-hidden rounded-xl border {term.is_current ? 'border-[var(--brand)]/30' : 'border-[var(--border)]'} bg-[var(--card)]">
  <div class="flex flex-wrap items-center gap-2.5 px-4 py-2.5">
    <span class="shrink-0 text-base leading-none {term.is_current ? 'text-[var(--brand)]' : 'text-[var(--fg-subtle)]'}" aria-hidden="true">
      {term.is_current ? '●' : '○'}
    </span>

    <span class="text-sm font-medium text-[var(--fg)]">{term.name}</span>
    {#if term.is_current}
      <span class="shrink-0 rounded-full bg-[var(--brand)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--brand)]">current</span>
    {/if}

    <span class="text-xs text-[var(--fg-muted)]">{classDisplayName}</span>
    {#if !assignmentActive}
      <span class="shrink-0 rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]" title="This class assignment is no longer active">
        Inactive assignment
      </span>
    {/if}

    <div class="ml-auto flex shrink-0 items-center gap-2">
      {#if enrollment?.fee_waived}
        <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400" title="Enrolled despite an outstanding fee balance">
          Fee waived
        </span>
      {/if}
      {#if term.results_locked}
        <span class="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-950/30 dark:text-red-400" title="This term's results are locked">
          Term locked
        </span>
      {/if}

      {#if isRegistered}
        {#if !term.is_current}
          <span class="text-amber-500" title="Not the current term — adding or removing subjects here needs a reason, and is only possible for staff who can approve scores">⚠</span>
        {/if}
        <button onclick={() => expanded = !expanded}
          class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          {subjectCount === undefined ? '…' : `${subjectCount} subject${subjectCount === 1 ? '' : 's'}`}
          <svg class="h-3.5 w-3.5 transition-transform duration-150 {expanded ? 'rotate-90' : ''}"
            fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      {:else}
        <span class="text-xs text-[var(--fg-subtle)]">{enrollment ? 'Withdrawn from this term' : 'Not registered'}</span>
        {#if canEdit}
          <button onclick={onRegister} disabled={isRegistering}
            class="rounded-lg px-3 py-1 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
            style="background: var(--brand)">
            {isRegistering ? '…' : 'Register'}
          </button>
        {/if}
      {/if}
    </div>
  </div>

  {#if registerError}
    <p class="border-t border-[var(--border)] px-4 py-1.5 text-[10px] text-red-500">{registerError}</p>
  {/if}

  {#if enrollment && enrollment.is_active && expanded}
    <div class="border-t border-[var(--border)] px-4 pb-3 pt-2.5">
      <SubjectRegistrationPanel {enrollment} compact={true} />
    </div>
  {/if}
</div>

<script lang="ts">
  import { reactiveQuery } from '$lib/query.svelte';
  import { getSubjectRoster } from '$lib/api/students';
  import RegisterStudentsModal from './RegisterStudentsModal.svelte';

  // Shown once Class → Subject → Category are all picked (the same point
  // the assessment list itself appears) when anyone in the class hasn't
  // been registered for this subject yet — a proactive nudge, not an
  // access-control gate: it shows unconditionally, even for a school
  // that's never touched subject registration before, since that's
  // exactly who this is meant to invite toward using it. Never rendered
  // for admin/approver — they manage rosters from the admin class-detail
  // page instead (parent only renders this component for a scoped
  // teacher, via `visible`).
  interface Props { classId: string; subjectId: string; termId: string; subjectName: string; visible: boolean; }
  const { classId, subjectId, termId, subjectName, visible }: Props = $props();

  // Shares its query key with SubjectRosterPanel/RegisterStudentsModal, so
  // opening the modal below is an instant cache hit, and closing it after a
  // save (which invalidates this same key) makes the banner disappear on
  // its own — no extra wiring needed.
  const rosterQ = reactiveQuery(() => ({
    queryKey: ['subject-roster', classId, subjectId, termId] as const,
    queryFn:  () => getSubjectRoster(classId, subjectId, termId),
    enabled:  visible && !!(classId && subjectId && termId),
    staleTime: 30_000,
  }));
  const hasUnregistered = $derived(($rosterQ.data ?? []).some(s => s.enrolled && !s.is_registered));

  let showModal = $state(false);
</script>

{#if visible && hasUnregistered}
  <div class="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm dark:border-amber-900 dark:bg-amber-950/30">
    <svg class="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
    </svg>
    <p class="flex-1 text-amber-800 dark:text-amber-300">
      You haven't registered all students in this class for {subjectName} yet.
    </p>
    <button onclick={() => showModal = true}
      class="min-h-[36px] shrink-0 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-amber-600">
      Register students
    </button>
  </div>
{/if}

{#if showModal}
  <RegisterStudentsModal {classId} {subjectId} {subjectName} onClose={() => showModal = false} />
{/if}

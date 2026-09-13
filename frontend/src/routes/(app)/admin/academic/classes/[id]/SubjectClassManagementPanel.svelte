<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listSubjectTeachers, removeSubjectTeacher, type SubjectTeacher } from '$lib/api/academic';
  import { listStaff } from '$lib/api/staff';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import SubjectRosterPanel from '$lib/components/SubjectRosterPanel.svelte';
  import CurriculumMaterialsPanel from './CurriculumMaterialsPanel.svelte';

  interface Props { subjectId: string; classId: string; yearId: string; termId: string; classSubjectId: string; }
  const { subjectId, classId, yearId, termId, classSubjectId }: Props = $props();

  const qc = useQueryClient();

  const subjTeachersQ = reactiveQuery<SubjectTeacher[]>(() => ({
    queryKey: ['subject-teachers', classId, yearId] as const,
    queryFn:  () => listSubjectTeachers(classId, yearId),
    enabled:  !!yearId,
    staleTime: 60_000,
  }));
  const staffQ = createQuery({ queryKey: ['staff'], queryFn: () => listStaff({ limit: 200, active_only: true }), staleTime: 5 * 60_000 });

  const staffMap       = $derived(new Map(($staffQ.data ?? []).map(s => [s.id, s])));
  const currentTeacherId = $derived(($subjTeachersQ.data ?? []).find(st => st.subject_id === subjectId)?.staff_member_id ?? null);
  const currentTeacher   = $derived(currentTeacherId ? staffMap.get(currentTeacherId) : null);

  let confirmUnassign = $state(false);
  const unassignMut = createMutation({
    mutationFn: () => removeSubjectTeacher(classId, subjectId, yearId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, yearId] });
      qc.invalidateQueries({ queryKey: ['class-timetable', classId, yearId] });
      qc.invalidateQueries({ queryKey: ['subject-summary', subjectId, termId] });
      toast.success('Teacher unassigned.');
    },
    onError: (e) => toast.error(apiError(e, 'Failed to unassign teacher.')),
  });

  const COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#ec4899','#14b8a6','#f97316'];
  function avatarBg(name: string): string {
    let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) & 0xff;
    return COLORS[h % COLORS.length];
  }
  function initials(name: string): string {
    const p = name.trim().split(/\s+/);
    return (p[0][0] + (p[1]?.[0] ?? '')).toUpperCase();
  }
</script>

<div class="border-t border-[var(--border)] bg-[var(--hover)]/40 px-4 py-3 space-y-3">
  <!-- Teacher -->
  <div class="flex flex-wrap items-center gap-2">
    <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Teacher</p>
    {#if !yearId}
      <span class="text-xs text-[var(--fg-subtle)]">Select a year first.</span>
    {:else if $subjTeachersQ.isPending}
      <div class="h-4 w-28 animate-pulse rounded-full bg-[var(--hover)]"></div>
    {:else if currentTeacher}
      <div class="flex items-center gap-1.5">
        <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[8px] font-bold text-white"
             style="background: {avatarBg(currentTeacher.display_name)}">{initials(currentTeacher.display_name)}</div>
        <span class="text-xs font-medium text-[var(--fg-muted)]">{currentTeacher.display_name}</span>
      </div>
    {:else}
      <span class="rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">No teacher</span>
    {/if}
    {#if yearId}
      {#if currentTeacher}
        <button onclick={() => confirmUnassign = true} class="flex min-h-[44px] items-center px-1 text-xs font-medium text-[var(--fg-subtle)] transition hover:text-red-500">
          Unassign
        </button>
      {:else}
        <span class="text-xs text-[var(--fg-subtle)]">Assign a teacher from the Timetable tab.</span>
      {/if}
    {/if}
  </div>

  <ConfirmModal
    open={confirmUnassign}
    title="Unassign teacher?"
    message="{currentTeacher?.display_name ?? 'This teacher'} will no longer be shown as the teacher for this subject in this class — this also clears the teacher shown on every period this subject appears on the class timetable. To assign someone new, use the Timetable tab."
    confirmLabel="Unassign"
    isPending={$unassignMut.isPending}
    onConfirm={() => { $unassignMut.mutate(); confirmUnassign = false; }}
    onCancel={() => confirmUnassign = false}
  />

  <!-- Students -->
  <div>
    <p class="mb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Students</p>
    <SubjectRosterPanel {classId} {subjectId} />
  </div>

  <div class="border-t border-[var(--border)] pt-3">
    <CurriculumMaterialsPanel {classSubjectId} />
  </div>
</div>

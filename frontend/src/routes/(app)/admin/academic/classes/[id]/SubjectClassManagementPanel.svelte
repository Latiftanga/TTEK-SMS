<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listSubjectTeachers, assignSubjectTeacher, type SubjectTeacher } from '$lib/api/academic';
  import { listStaff } from '$lib/api/staff';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
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

  const teachingStaff = $derived(($staffQ.data ?? []).filter(s => s.staff_type === 'TEACHING'));
  const staffMap       = $derived(new Map(($staffQ.data ?? []).map(s => [s.id, s])));
  const currentTeacherId = $derived(($subjTeachersQ.data ?? []).find(st => st.subject_id === subjectId)?.staff_member_id ?? null);
  const currentTeacher   = $derived(currentTeacherId ? staffMap.get(currentTeacherId) : null);

  let editing       = $state(false);
  let changeStaffId = $state('');
  let changeError   = $state('');

  function startChange() {
    changeStaffId = currentTeacherId ?? '';
    changeError = '';
    editing = true;
  }

  const changeMut = createMutation({
    mutationFn: () => assignSubjectTeacher(classId, { subject_id: subjectId, staff_member_id: changeStaffId, academic_year_id: yearId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, yearId] });
      qc.invalidateQueries({ queryKey: ['subject-summary', subjectId, termId] });
      editing = false; changeStaffId = ''; changeError = '';
      toast.success('Teacher updated.');
    },
    onError: (e) => { changeError = apiError(e, 'Failed to assign teacher.'); },
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

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
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
    {#if yearId && !editing}
      <button onclick={startChange} class="flex min-h-[44px] items-center px-1 text-xs font-medium transition hover:underline" style="color:var(--brand)">
        {currentTeacher ? 'Change' : 'Assign'}
      </button>
    {/if}
  </div>

  {#if editing}
    <div class="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
      <select bind:value={changeStaffId} class={sel}>
        <option value="">Select teacher…</option>
        {#each teachingStaff as s (s.id)}<option value={s.id}>{s.display_name}</option>{/each}
      </select>
      {#if changeError}<p class="text-xs text-red-500">{changeError}</p>{/if}
      <div class="flex gap-2">
        <button onclick={() => { changeError = ''; if (!changeStaffId) { changeError = 'Select a teacher.'; return; } $changeMut.mutate(); }}
          disabled={$changeMut.isPending}
          class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background:var(--brand)">{$changeMut.isPending ? 'Saving…' : 'Confirm'}</button>
        <button onclick={() => { editing = false; changeError = ''; }}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Cancel</button>
      </div>
    </div>
  {/if}

  <!-- Students -->
  <div>
    <p class="mb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Students</p>
    <SubjectRosterPanel {classId} {subjectId} />
  </div>

  <div class="border-t border-[var(--border)] pt-3">
    <CurriculumMaterialsPanel {classSubjectId} />
  </div>
</div>

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import {
    getClassTeacher, listSubjectTeachers, assignClassTeacher, assignSubjectTeacher,
    listClassSubjects, listSubjects,
    type AcademicYear, type AcademicTerm,
  } from '$lib/api/academic';
  import { listStaff } from '$lib/api/staff';
  import { toast } from '$lib/stores/toast';

  interface Props {
    classId: string;
    currentYearId: string;
    currentTermId: string;
    years: AcademicYear[];
    terms: AcademicTerm[];
  }
  const { classId, currentYearId, currentTermId, years, terms }: Props = $props();

  const qc = useQueryClient();

  // ── Selectors for context ─────────────────────────────────────────────────────
  let yearId = $state('');
  let termId = $state('');

  $effect(() => { if (currentYearId && !yearId) yearId = currentYearId; });
  $effect(() => { if (currentTermId && !termId) termId = currentTermId; });

  const termsForYear = $derived(terms.filter(t => t.academic_year_id === yearId)
    .sort((a, b) => a.start_date.localeCompare(b.start_date)));

  // ── Queries ───────────────────────────────────────────────────────────────────
  const staffQ   = createQuery({ queryKey: ['staff'],               queryFn: () => listStaff({ limit: 200, active_only: true }), staleTime: 5 * 60_000 });
  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],            queryFn: listSubjects, staleTime: 5 * 60_000 });

  const ctOpts = writable({ queryKey: ['class-teacher', classId, yearId] as const, queryFn: () => getClassTeacher(classId, yearId), enabled: !!yearId, staleTime: 60_000 });
  $effect(() => { const y = yearId; ctOpts.set({ queryKey: ['class-teacher', classId, y] as const, queryFn: () => getClassTeacher(classId, y), enabled: !!y, staleTime: 60_000 }); });
  const classTeacherQ = createQuery(ctOpts);

  const stOpts = writable({ queryKey: ['subject-teachers', classId, termId] as const, queryFn: () => listSubjectTeachers(classId, termId), enabled: !!termId, staleTime: 60_000 });
  $effect(() => { const t = termId; stOpts.set({ queryKey: ['subject-teachers', classId, t] as const, queryFn: () => listSubjectTeachers(classId, t), enabled: !!t, staleTime: 60_000 }); });
  const subjTeachersQ = createQuery(stOpts);

  // ── Derived maps ──────────────────────────────────────────────────────────────
  const staffMap   = $derived(new Map(($staffQ.data ?? []).map(s => [s.id, s])));
  const subjectMap = $derived(new Map(($allSubjQ.data ?? []).map(s => [s.id, s])));
  const classSubjects = $derived($clsSubjQ.data ?? []);

  const classTeacher   = $derived($classTeacherQ.data ?? null);
  const ctName         = $derived(classTeacher ? (staffMap.get(classTeacher.staff_member_id)?.display_name ?? null) : null);
  const subjTeachers   = $derived($subjTeachersQ.data ?? []);
  const assignedSubjIds = $derived(new Set(subjTeachers.map(st => st.subject_id)));

  // ── Class teacher assignment ───────────────────────────────────────────────────
  let showCtForm = $state(false);
  let ctStaffId  = $state('');
  let ctErr      = $state('');

  const ctMut = createMutation({
    mutationFn: () => assignClassTeacher(classId, { staff_member_id: ctStaffId, academic_year_id: yearId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-teacher', classId, yearId] });
      qc.invalidateQueries({ queryKey: ['staff'] });
      showCtForm = false; ctStaffId = ''; ctErr = '';
      toast.success('Class teacher assigned.');
    },
    onError: (e: unknown) => { ctErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not assign.'; },
  });

  // ── Subject teacher assignment ────────────────────────────────────────────────
  let showStForm   = $state(false);
  let stSubjectId  = $state('');
  let stStaffId    = $state('');
  let stErr        = $state('');

  const stMut = createMutation({
    mutationFn: () => assignSubjectTeacher(classId, { subject_id: stSubjectId, staff_member_id: stStaffId, academic_term_id: termId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, termId] });
      showStForm = false; stSubjectId = ''; stStaffId = ''; stErr = '';
      toast.success('Subject teacher assigned.');
    },
    onError: (e: unknown) => { stErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not assign.'; },
  });

  const sel = "w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition";
</script>

<!-- Context selectors -->
<div class="mb-5 flex flex-wrap gap-3">
  <div class="min-w-[160px]">
    <label class="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Academic year</label>
    <select bind:value={yearId} class={sel}>
      <option value="">Select year…</option>
      {#each [...years].sort((a,b) => b.start_date.localeCompare(a.start_date)) as y}
        <option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>
      {/each}
    </select>
  </div>
  <div class="min-w-[180px]">
    <label class="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Term (for subject teachers)</label>
    <select bind:value={termId} class={sel}>
      <option value="">Select term…</option>
      {#each termsForYear as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
    </select>
  </div>
</div>

<!-- Class teacher -->
<div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <div class="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
    <p class="text-xs font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Class teacher</p>
    {#if yearId}
      <button onclick={() => { showCtForm = !showCtForm; ctStaffId = classTeacher?.staff_member_id ?? ''; ctErr = ''; }}
        class="text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
        {classTeacher ? 'Change' : 'Assign'}
      </button>
    {/if}
  </div>
  <div class="px-5 py-4">
    {#if !yearId}
      <p class="text-sm text-[var(--fg-subtle)]">Select an academic year above.</p>
    {:else if $classTeacherQ.isPending}
      <div class="h-8 w-48 animate-pulse rounded-lg bg-[var(--hover)]"></div>
    {:else if ctName}
      <p class="font-semibold text-[var(--fg)]">{ctName}</p>
      <p class="text-xs text-[var(--fg-muted)]">{staffMap.get(classTeacher!.staff_member_id)?.staff_number ?? ''}</p>
    {:else}
      <p class="text-sm italic text-[var(--fg-muted)]">No class teacher assigned for this year.</p>
    {/if}
    {#if showCtForm && yearId}
      <div class="mt-3 space-y-2 border-t border-[var(--border)] pt-3">
        <select bind:value={ctStaffId} class={sel}>
          <option value="">Select teacher…</option>
          {#each $staffQ.data ?? [] as s}<option value={s.id}>{s.display_name} — {s.staff_number}</option>{/each}
        </select>
        {#if ctErr}<p class="text-xs text-red-500">{ctErr}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => { ctErr=''; if(!ctStaffId){ctErr='Select a teacher.'; return;} $ctMut.mutate(); }}
            disabled={$ctMut.isPending}
            class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background:var(--brand)">{$ctMut.isPending ? 'Assigning…' : 'Confirm'}</button>
          <button onclick={() => { showCtForm = false; ctErr = ''; }}
            class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
        </div>
      </div>
    {/if}
  </div>
</div>

<!-- Subject teachers -->
<div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <div class="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
    <p class="text-xs font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Subject teachers</p>
    {#if termId && classSubjects.length > 0}
      <button onclick={() => { showStForm = !showStForm; stSubjectId = ''; stStaffId = ''; stErr = ''; }}
        class="flex items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
        Assign
      </button>
    {/if}
  </div>

  {#if !termId}
    <p class="px-5 py-4 text-sm text-[var(--fg-subtle)]">Select a term above to see subject teachers.</p>
  {:else if $subjTeachersQ.isPending}
    <div class="space-y-2 p-4">{#each [1,2,3] as _}<div class="h-10 animate-pulse rounded-lg bg-[var(--hover)]"></div>{/each}</div>
  {:else}
    <!-- Subjects that have a teacher -->
    {#each classSubjects as cs (cs.subject_id)}
      {@const subj    = subjectMap.get(cs.subject_id)}
      {@const teacher = subjTeachers.find(st => st.subject_id === cs.subject_id)}
      {@const tName   = teacher ? (staffMap.get(teacher.staff_member_id)?.display_name ?? null) : null}
      <div class="flex items-center gap-3 border-b border-[var(--border)] px-5 py-3 last:border-0">
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-[var(--fg)]">{subj?.name ?? '—'}</p>
          <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{subj?.code ?? ''}</p>
        </div>
        {#if tName}
          <span class="text-sm text-[var(--fg-muted)]">{tName}</span>
        {:else}
          <span class="rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">Unassigned</span>
        {/if}
      </div>
    {/each}
    {#if classSubjects.length === 0}
      <p class="px-5 py-4 text-sm text-[var(--fg-muted)]">No subjects assigned to this class yet. Add subjects on the Subjects tab first.</p>
    {/if}
  {/if}

  <!-- Assign subject teacher inline form -->
  {#if showStForm && termId}
    <div class="border-t border-[var(--border)] p-5 space-y-3">
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Subject</label>
          <select bind:value={stSubjectId} class={sel}>
            <option value="">Select subject…</option>
            {#each classSubjects as cs}
              {@const s = subjectMap.get(cs.subject_id)}
              {#if s}<option value={cs.subject_id}>{s.name}</option>{/if}
            {/each}
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Teacher</label>
          <select bind:value={stStaffId} class={sel}>
            <option value="">Select teacher…</option>
            {#each $staffQ.data ?? [] as s}<option value={s.id}>{s.display_name}</option>{/each}
          </select>
        </div>
      </div>
      {#if stErr}<p class="text-xs text-red-500">{stErr}</p>{/if}
      <div class="flex gap-2">
        <button onclick={() => { stErr=''; if(!stSubjectId){stErr='Select a subject.'; return;} if(!stStaffId){stErr='Select a teacher.'; return;} $stMut.mutate(); }}
          disabled={$stMut.isPending}
          class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background:var(--brand)">{$stMut.isPending ? 'Assigning…' : 'Assign'}</button>
        <button onclick={() => { showStForm = false; stErr = ''; }}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
      </div>
    </div>
  {/if}
</div>

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import {
    listClassSubjects, listSubjects, assignSubjects, removeClassSubject,
    listYears, listSubjectTeachers, assignSubjectTeacher,
  } from '$lib/api/academic';
  import { listStaff } from '$lib/api/staff';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';

  interface Props { classId: string; }
  const { classId }: Props = $props();

  const qc = useQueryClient();

  // ── Queries ───────────────────────────────────────────────────────────────────
  const yearsQ   = createQuery({ queryKey: ['academic-years'],        queryFn: listYears,                                        staleTime: 5 * 60_000 });
  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId),               staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],               queryFn: listSubjects,                                     staleTime: 5 * 60_000 });
  const staffQ   = createQuery({ queryKey: ['staff'],                  queryFn: () => listStaff({ limit: 200, active_only: true }), staleTime: 5 * 60_000 });

  // ── Term selection (defaults to current term) ─────────────────────────────────
  let termId = $state('');
  $effect(() => {
    if (termId) return;
    for (const y of $yearsQ.data ?? []) {
      const cur = y.terms.find(t => t.is_current);
      if (cur) { termId = cur.id; break; }
    }
  });

  // Use writable store so options update reactively without the function form (which triggers
  // TanStack's queryKey validation on mount even when enabled:false)
  const subjTeachersOpts = writable({ queryKey: ['subject-teachers', classId, ''] as string[], queryFn: () => listSubjectTeachers(classId, ''), enabled: false, staleTime: 60_000 });
  $effect(() => {
    const t = termId;
    subjTeachersOpts.set({ queryKey: ['subject-teachers', classId, t], queryFn: () => listSubjectTeachers(classId, t), enabled: !!t, staleTime: 60_000 });
  });
  const subjTeachersQ = createQuery(subjTeachersOpts);

  // ── Derived ───────────────────────────────────────────────────────────────────
  const classSubjects    = $derived($clsSubjQ.data ?? []);
  const subjectMap       = $derived(new Map(($allSubjQ.data ?? []).map(s => [s.id, s])));
  const staffMap         = $derived(new Map(($staffQ.data ?? []).map(s => [s.id, s])));
  const teacherBySubject = $derived(new Map(($subjTeachersQ.data ?? []).map(st => [st.subject_id, st.staff_member_id])));
  const unassignedSubjs  = $derived(($allSubjQ.data ?? []).filter(s => s.is_active && !classSubjects.some(cs => cs.subject_id === s.id)));

  // ── Add subject + teacher ─────────────────────────────────────────────────────
  let showAdd      = $state(false);
  let newSubjectId = $state('');
  let newTeacherId = $state('');
  let addError     = $state('');

  // Teacher required only when a term is selected
  const canAdd = $derived(!!newSubjectId && (!termId || !!newTeacherId));

  const addMut = createMutation({
    mutationFn: async () => {
      await assignSubjects(classId, [newSubjectId]);
      if (termId && newTeacherId)
        await assignSubjectTeacher(classId, { subject_id: newSubjectId, staff_member_id: newTeacherId, academic_term_id: termId });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, termId] });
      showAdd = false; newSubjectId = ''; newTeacherId = ''; addError = '';
      toast.success('Subject assigned.');
    },
    onError: (e) => { addError = apiError(e, 'Failed to assign subject.'); },
  });

  // ── Change / assign teacher per subject ───────────────────────────────────────
  let changingId    = $state('');
  let changeStaffId = $state('');
  let changeError   = $state('');

  function startChange(subjectId: string) {
    changingId    = subjectId;
    changeStaffId = teacherBySubject.get(subjectId) ?? '';
    changeError   = '';
  }

  const changeMut = createMutation({
    mutationFn: () => assignSubjectTeacher(classId, { subject_id: changingId, staff_member_id: changeStaffId, academic_term_id: termId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, termId] });
      changingId = ''; changeStaffId = ''; changeError = '';
      toast.success('Teacher updated.');
    },
    onError: (e) => { changeError = apiError(e, 'Failed to assign teacher.'); },
  });

  // ── Remove subject ────────────────────────────────────────────────────────────
  const removeMut = createMutation({
    mutationFn: (subjectId: string) => removeClassSubject(classId, subjectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, termId] });
      toast.success('Subject removed.');
    },
    onError: (e) => toast.error(apiError(e, 'Failed to remove subject.')),
  });

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

<div class="space-y-4">

  <!-- Term selector -->
  <div class="w-56">
    <label class="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Term</label>
    <select bind:value={termId} class={sel}>
      <option value="">Select term…</option>
      {#each $yearsQ.data ?? [] as y (y.id)}
        {#if y.terms.length}
          <optgroup label={y.name}>
            {#each y.terms as t (t.id)}
              <option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>
            {/each}
          </optgroup>
        {/if}
      {/each}
    </select>
  </div>

  <!-- Subject list -->
  {#if $clsSubjQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if classSubjects.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-12 text-center">
      <p class="text-sm font-medium text-[var(--fg-muted)]">No subjects assigned yet.</p>
      <button onclick={() => showAdd = true}
        class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition"
        style="background: var(--brand)">Add first subject</button>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
          {classSubjects.length} subject{classSubjects.length !== 1 ? 's' : ''}
        </p>
        <button onclick={() => { showAdd = !showAdd; newSubjectId = ''; newTeacherId = ''; addError = ''; }}
          class="flex items-center gap-1 text-xs font-semibold hover:opacity-70 transition" style="color:var(--brand)">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add subject
        </button>
      </div>

      {#each classSubjects as cs (cs.subject_id)}
        {@const subj     = subjectMap.get(cs.subject_id)}
        {@const staffId  = teacherBySubject.get(cs.subject_id)}
        {@const teacher  = staffId ? staffMap.get(staffId) : null}
        {@const editing  = changingId === cs.subject_id}
        <div class="border-b border-[var(--border)] last:border-0">
          <!-- Subject row -->
          <div class="flex items-center gap-3 px-4 py-3">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-[var(--fg)]">{subj?.name ?? '—'}</p>
              <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{subj?.code ?? ''}</p>
            </div>
            <!-- Teacher cell -->
            {#if !termId}
              <span class="text-xs text-[var(--fg-subtle)]">—</span>
            {:else if $subjTeachersQ.isPending}
              <span class="h-3.5 w-24 animate-pulse rounded bg-[var(--hover)]"></span>
            {:else if teacher}
              <span class="text-sm text-[var(--fg-muted)]">{teacher.display_name}</span>
            {:else}
              <span class="rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">Unassigned</span>
            {/if}
            <!-- Actions -->
            {#if termId && !editing}
              <button onclick={() => startChange(cs.subject_id)}
                class="shrink-0 text-xs font-medium text-[var(--brand)] hover:underline transition">
                {teacher ? 'Change' : 'Assign'}
              </button>
            {/if}
            <button onclick={() => $removeMut.mutate(cs.subject_id)}
              disabled={$removeMut.isPending}
              class="shrink-0 text-xs text-[var(--fg-muted)] hover:text-red-500 disabled:opacity-40 transition">
              Remove
            </button>
          </div>

          <!-- Inline teacher change form -->
          {#if editing}
            <div class="border-t border-[var(--border)] bg-[var(--hover)]/40 px-4 py-3 space-y-2">
              <select bind:value={changeStaffId} class={sel}>
                <option value="">Select teacher…</option>
                {#each $staffQ.data ?? [] as s (s.id)}<option value={s.id}>{s.display_name}</option>{/each}
              </select>
              {#if changeError}<p class="text-xs text-red-500">{changeError}</p>{/if}
              <div class="flex gap-2">
                <button onclick={() => { changeError = ''; if (!changeStaffId) { changeError = 'Select a teacher.'; return; } $changeMut.mutate(); }}
                  disabled={$changeMut.isPending}
                  class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition"
                  style="background:var(--brand)">{$changeMut.isPending ? 'Saving…' : 'Confirm'}</button>
                <button onclick={() => { changingId = ''; changeError = ''; }}
                  class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <!-- Add subject + teacher form -->
  {#if showAdd}
    {#if unassignedSubjs.length === 0}
      <p class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-[var(--fg-muted)]">
        All available subjects are already assigned to this class.
      </p>
    {:else}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
        <p class="text-xs font-semibold text-[var(--fg)]">Add subject</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Subject *</label>
            <select bind:value={newSubjectId} class={sel}>
              <option value="">Select subject…</option>
              {#each unassignedSubjs as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
              Teacher{termId ? ' *' : ' (select a term first)'}
            </label>
            <select bind:value={newTeacherId} disabled={!termId} class={sel}>
              <option value="">Select teacher…</option>
              {#each $staffQ.data ?? [] as s (s.id)}<option value={s.id}>{s.display_name}</option>{/each}
            </select>
          </div>
        </div>
        {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $addMut.mutate()} disabled={$addMut.isPending || !canAdd}
            class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition"
            style="background:var(--brand)">{$addMut.isPending ? 'Saving…' : 'Add'}</button>
          <button onclick={() => { showAdd = false; newSubjectId = ''; newTeacherId = ''; addError = ''; }}
            class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
        </div>
      </div>
    {/if}
  {/if}

</div>

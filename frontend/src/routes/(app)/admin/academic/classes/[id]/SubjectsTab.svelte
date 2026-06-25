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
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { classId: string; }
  const { classId }: Props = $props();

  const qc = useQueryClient();

  const yearsQ   = createQuery({ queryKey: ['academic-years'],          queryFn: listYears,                                        staleTime: 5 * 60_000 });
  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId),                 staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],                queryFn: listSubjects,                                     staleTime: 5 * 60_000 });
  const staffQ   = createQuery({ queryKey: ['staff'],                   queryFn: () => listStaff({ limit: 200, active_only: true }), staleTime: 5 * 60_000 });

  // ── Term selection ────────────────────────────────────────────────────────────
  let termId = $state('');
  $effect(() => {
    if (termId) return;
    for (const y of $yearsQ.data ?? []) {
      const cur = y.terms.find(t => t.is_current);
      if (cur) { termId = cur.id; break; }
    }
  });

  // Writable store pattern — avoids TanStack's queryKey validation on mount
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
  const unassignedCount  = $derived(classSubjects.filter(cs => termId && !teacherBySubject.has(cs.subject_id)).length);

  // ── Add subject + teacher ─────────────────────────────────────────────────────
  let showAdd      = $state(false);
  let newSubjectId = $state('');
  let newTeacherId = $state('');
  let addError     = $state('');

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

  // ── Change / assign teacher ───────────────────────────────────────────────────
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
  let confirmRemoveId = $state<string | null>(null);
  const removeMut = createMutation({
    mutationFn: (subjectId: string) => removeClassSubject(classId, subjectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      qc.invalidateQueries({ queryKey: ['subject-teachers', classId, termId] });
      toast.success('Subject removed.');
    },
    onError: (e) => toast.error(apiError(e, 'Failed to remove subject.')),
  });

  // Avatar helpers
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
  const selSm = 'rounded-xl border border-[var(--border)] bg-[var(--bg)] py-1.5 pl-2.5 pr-7 text-xs text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition appearance-none';
</script>

<div class="space-y-4">
  {#if $clsSubjQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>

  {:else if classSubjects.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-12 text-center">
      <svg class="mx-auto mb-3 h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.25" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>
      </svg>
      <p class="text-sm font-medium text-[var(--fg-muted)]">No subjects assigned yet.</p>
      <button onclick={() => showAdd = true}
        class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">Add first subject</button>
    </div>

  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <!-- Card header: count + unassigned warning + term selector + add button -->
      <div class="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div class="flex flex-1 flex-wrap items-center gap-2">
          <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
            {classSubjects.length} subject{classSubjects.length !== 1 ? 's' : ''}
          </p>
          {#if termId && unassignedCount > 0}
            <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
              {unassignedCount} without teacher
            </span>
          {/if}
        </div>
        <!-- Term selector (compact, inline) -->
        <div class="relative shrink-0">
          <select bind:value={termId} class={selSm}>
            <option value="">No term</option>
            {#each $yearsQ.data ?? [] as y (y.id)}
              {#if y.terms.length}
                <optgroup label={y.name}>
                  {#each y.terms as t (t.id)}
                    <option value={t.id}>{t.name}{t.is_current ? ' ✓' : ''}</option>
                  {/each}
                </optgroup>
              {/if}
            {/each}
          </select>
          <svg class="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
          </svg>
        </div>
        <button onclick={() => { showAdd = !showAdd; newSubjectId = ''; newTeacherId = ''; addError = ''; }}
          class="flex shrink-0 items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add
        </button>
      </div>

      <!-- Subject rows -->
      {#each classSubjects as cs (cs.subject_id)}
        {@const subj    = subjectMap.get(cs.subject_id)}
        {@const staffId = teacherBySubject.get(cs.subject_id)}
        {@const teacher = staffId ? staffMap.get(staffId) : null}
        {@const editing = changingId === cs.subject_id}

        <div class="border-b border-[var(--border)] last:border-0">
          <div class="flex items-center gap-3 px-4 py-3">
            <!-- Subject name + code -->
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-[var(--fg)]">{subj?.name ?? '—'}</p>
              {#if subj?.code}
                <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{subj.code}</p>
              {/if}
            </div>

            <!-- Teacher chip -->
            {#if !termId}
              <span class="shrink-0 text-xs text-[var(--fg-subtle)]">—</span>
            {:else if $subjTeachersQ.isPending}
              <div class="h-4 w-28 animate-pulse rounded-full bg-[var(--hover)]"></div>
            {:else if teacher}
              <div class="flex shrink-0 items-center gap-1.5">
                <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[8px] font-bold text-white"
                     style="background: {avatarBg(teacher.display_name)}">
                  {initials(teacher.display_name)}
                </div>
                <span class="max-w-[120px] truncate text-xs font-medium text-[var(--fg-muted)]">{teacher.display_name}</span>
              </div>
            {:else}
              <span class="shrink-0 rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">No teacher</span>
            {/if}

            <!-- Actions -->
            {#if termId && !editing}
              <button onclick={() => startChange(cs.subject_id)}
                class="shrink-0 text-xs font-medium transition hover:underline" style="color:var(--brand)">
                {teacher ? 'Change' : 'Assign'}
              </button>
            {/if}
            <button onclick={() => confirmRemoveId = cs.subject_id} disabled={$removeMut.isPending}
              class="shrink-0 text-xs text-[var(--fg-subtle)] transition hover:text-red-500 disabled:opacity-40">
              Remove
            </button>
          </div>

          <!-- Inline teacher change form -->
          {#if editing}
            <div class="border-t border-[var(--border)] bg-[var(--hover)]/40 px-4 py-3 space-y-2">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
                Assign teacher for {subj?.name ?? 'subject'}
              </p>
              <select bind:value={changeStaffId} class={sel}>
                <option value="">Select teacher…</option>
                {#each $staffQ.data ?? [] as s (s.id)}<option value={s.id}>{s.display_name}</option>{/each}
              </select>
              {#if changeError}<p class="text-xs text-red-500">{changeError}</p>{/if}
              <div class="flex gap-2">
                <button onclick={() => { changeError = ''; if (!changeStaffId) { changeError = 'Select a teacher.'; return; } $changeMut.mutate(); }}
                  disabled={$changeMut.isPending}
                  class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                  style="background:var(--brand)">{$changeMut.isPending ? 'Saving…' : 'Confirm'}</button>
                <button onclick={() => { changingId = ''; changeError = ''; }}
                  class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Cancel</button>
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
            class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background:var(--brand)">{$addMut.isPending ? 'Saving…' : 'Add'}</button>
          <button onclick={() => { showAdd = false; newSubjectId = ''; newTeacherId = ''; addError = ''; }}
            class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Cancel</button>
        </div>
      </div>
    {/if}
  {/if}
</div>

<ConfirmModal
  open={!!confirmRemoveId}
  title="Remove subject?"
  message="This subject and its teacher assignment will be removed from the class. The subject itself is not deleted."
  confirmLabel="Remove"
  isPending={$removeMut.isPending}
  onConfirm={() => { $removeMut.mutate(confirmRemoveId!); confirmRemoveId = null; }}
  onCancel={() => confirmRemoveId = null}
/>

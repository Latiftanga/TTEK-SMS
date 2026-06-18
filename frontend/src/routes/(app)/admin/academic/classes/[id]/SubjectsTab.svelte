<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listClassSubjects, listSubjects, assignSubjects, removeClassSubject,
    listSubjectTeachers, assignSubjectTeacher,
    type ClassSubject, type Subject, type SubjectTeacher,
  } from '$lib/api/academic';
  import { listStaff, type StaffSummary } from '$lib/api/staff';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';

  interface Props { classId: string; selectedTermId: string; }
  const { classId, selectedTermId }: Props = $props();

  const qc = useQueryClient();

  const clsSubjQuery   = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });
  const allSubjQuery   = createQuery({ queryKey: ['subjects'], queryFn: listSubjects, staleTime: 5 * 60_000 });
  const staffQuery     = createQuery({ queryKey: ['staff'], queryFn: () => listStaff({ limit: 200 }), staleTime: 5 * 60_000 });
  const stchrsQuery    = createQuery({
    queryKey: ['subject-teachers', classId, selectedTermId],
    queryFn: () => listSubjectTeachers(classId, selectedTermId),
    enabled: !!selectedTermId,
    staleTime: 60_000,
  });

  const classSubjects   = $derived<ClassSubject[]>($clsSubjQuery.data ?? []);
  const allSubjects     = $derived<Subject[]>($allSubjQuery.data ?? []);
  const staff           = $derived<StaffSummary[]>($staffQuery.data ?? []);
  const subjectTeachers = $derived<SubjectTeacher[]>($stchrsQuery.data ?? []);

  const assignedIds = $derived(new Set(classSubjects.map(cs => cs.subject_id)));
  const unassigned  = $derived(allSubjects.filter(s => s.is_active && !assignedIds.has(s.id)));
  const subjectMap  = $derived(new Map(allSubjects.map(s => [s.id, s])));
  const staffMap    = $derived(new Map(staff.map(s => [s.id, s])));
  const stMap       = $derived(new Map(subjectTeachers.map(st => [st.subject_id, st])));

  let showAdd   = $state(false);
  let addSearch = $state('');
  let toAdd     = $state(new Set<string>());
  const filtered = $derived(unassigned.filter(s =>
    !addSearch.trim() || s.name.toLowerCase().includes(addSearch.toLowerCase()) || s.code.toLowerCase().includes(addSearch.toLowerCase())
  ));
  const addMut = createMutation({
    mutationFn: () => assignSubjects(classId, [...toAdd]),
    onSuccess: (added) => {
      qc.invalidateQueries({ queryKey: ['class-subjects'] });
      showAdd = false; toAdd = new Set(); addSearch = '';
      toast.success(added.length ? `${added.length} subject${added.length !== 1 ? 's' : ''} added.` : 'Subjects updated.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to add subjects. Check your permissions.';
      toast.error(msg);
    },
  });
  function toggleAdd(id: string) { const n = new Set(toAdd); n.has(id) ? n.delete(id) : n.add(id); toAdd = n; }

  let removingId = $state<string | null>(null);
  const removeMut = createMutation({
    mutationFn: (sid: string) => removeClassSubject(classId, sid),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['class-subjects'] }); removingId = null; },
    onError: (e: unknown) => {
      removingId = null;
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to remove subject.';
      toast.error(msg);
    },
  });

  let assigningSubjectId = $state<string | null>(null);
  let assignSTStaffId    = $state('');
  let stSearch           = $state('');
  const stFiltered = $derived(staff.filter(s => s.is_active && s.staff_category === 'TEACHING' && (!stSearch || s.display_name.toLowerCase().includes(stSearch.toLowerCase()))));
  const assignSTMut = createMutation({
    mutationFn: ({ subjectId, staffId }: { subjectId: string; staffId: string }) =>
      assignSubjectTeacher(classId, { subject_id: subjectId, staff_member_id: staffId, academic_term_id: selectedTermId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subject-teachers'] });
      assigningSubjectId = null; assignSTStaffId = '';
      toast.success('Subject teacher assigned.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to assign teacher. Check your permissions.';
      toast.error(msg);
    },
  });
</script>

<div class="mb-4 flex items-center justify-between">
  <p class="text-sm text-[var(--fg-muted)]">
    {classSubjects.length} subject{classSubjects.length !== 1 ? 's' : ''} assigned
  </p>
  <button
    onclick={() => { showAdd = true; toAdd = new Set(); addSearch = ''; }}
    class="h-8 rounded-lg bg-[var(--brand)] px-3 text-xs font-medium text-white transition-opacity hover:opacity-90"
  >+ Add Subjects</button>
</div>

{#if $clsSubjQuery.isLoading}
  <div class="space-y-2">{#each [1,2,3] as _}<div class="skeleton h-12"></div>{/each}</div>
{:else if classSubjects.length === 0}
  <EmptyState
    iconPath="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
    title="No subjects assigned yet."
    description="Add subjects to this class so teachers can be assigned and scores recorded."
    action={() => showAdd = true}
    actionLabel="Add subjects"
  />
{:else}
  <div class="overflow-x-auto rounded-xl border border-[var(--border)]">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-[var(--border)]">
          <th class="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Subject</th>
          <th class="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Code</th>
          <th class="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
            Teacher
            {#if !selectedTermId}<span class="ml-1 text-[10px] font-normal normal-case tracking-normal text-[var(--fg-subtle)] italic">(select a term)</span>{/if}
          </th>
          <th class="w-44 px-4 py-2.5"></th>
        </tr>
      </thead>
      <tbody class="divide-y divide-[var(--border)]">
        {#each classSubjects as cs}
          {@const subject = subjectMap.get(cs.subject_id)}
          {@const st = stMap.get(cs.subject_id)}
          {@const teacher = st ? staffMap.get(st.staff_member_id) : null}
          <tr class="bg-[var(--card)] transition-colors hover:bg-[var(--hover)]">
            <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{subject?.name ?? '—'}</td>
            <td class="px-4 py-2.5 text-[var(--fg-muted)]">{subject?.code ?? '—'}</td>
            <td class="px-4 py-2.5 text-[var(--fg-muted)]">
              {#if selectedTermId}
                {#if teacher}
                  {teacher.display_name}
                {:else}
                  <span class="italic text-[var(--fg-subtle)]">Unassigned</span>
                {/if}
              {:else}
                <span class="text-[var(--fg-subtle)]">—</span>
              {/if}
            </td>
            <td class="px-4 py-2.5 text-right">
              <div class="flex items-center justify-end gap-3">
                {#if selectedTermId}
                  <button
                    onclick={() => { assigningSubjectId = cs.subject_id; assignSTStaffId = st?.staff_member_id ?? ''; stSearch = ''; }}
                    class="whitespace-nowrap text-xs text-[var(--brand)] hover:underline"
                  >{st ? 'Change teacher' : 'Assign teacher'}</button>
                {/if}
                <button
                  onclick={() => { removingId = cs.subject_id; $removeMut.mutate(cs.subject_id); }}
                  disabled={$removeMut.isPending && removingId === cs.subject_id}
                  class="whitespace-nowrap text-xs text-red-500 hover:text-red-700 disabled:opacity-40"
                >Remove</button>
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

{#if showAdd}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="flex w-full max-w-md flex-col gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="text-lg font-semibold text-[var(--fg)]">Add Subjects</h2>
      <input bind:value={addSearch} placeholder="Search subjects…"
        class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]" />
      <div class="max-h-60 overflow-y-auto divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
        {#if filtered.length === 0}
          <p class="px-3 py-4 text-center text-sm text-[var(--fg-muted)]">
            {unassigned.length === 0 ? 'All subjects already assigned.' : 'No matches.'}
          </p>
        {:else}
          {#each filtered as s}
            <label class="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-[var(--hover)]">
              <input type="checkbox" checked={toAdd.has(s.id)} onchange={() => toggleAdd(s.id)} class="rounded" />
              <span class="text-sm text-[var(--fg)]">{s.name}</span>
              <span class="ml-auto text-xs text-[var(--fg-muted)]">{s.code}</span>
            </label>
          {/each}
        {/if}
      </div>
      <div class="flex items-center justify-between">
        <span class="text-xs text-[var(--fg-muted)]">{toAdd.size} selected</span>
        <div class="flex gap-3">
          <button onclick={() => showAdd = false} class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
          <button onclick={() => $addMut.mutate()} disabled={toAdd.size === 0 || $addMut.isPending}
            class="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:opacity-90">
            {$addMut.isPending ? 'Adding…' : `Add ${toAdd.size || ''}`}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

{#if assigningSubjectId}
  {@const subjectName = subjectMap.get(assigningSubjectId)?.name ?? ''}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="mb-1 text-lg font-semibold text-[var(--fg)]">Assign Teacher</h2>
      <p class="mb-4 text-sm text-[var(--fg-muted)]">Subject: {subjectName}</p>
      <input bind:value={stSearch} placeholder="Search staff…"
        class="mb-2 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]" />
      <div class="max-h-52 overflow-y-auto divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
        {#each stFiltered as s}
          <button onclick={() => assignSTStaffId = s.id}
            class="w-full px-3 py-2 text-left text-sm hover:bg-[var(--hover)] {assignSTStaffId === s.id ? 'bg-[var(--hover)] font-medium' : ''}">
            {s.display_name}{s.position_names?.length ? ` · ${s.position_names.join(', ')}` : ''}
          </button>
        {/each}
      </div>
      <div class="mt-4 flex justify-end gap-3">
        <button onclick={() => assigningSubjectId = null} class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
        <button onclick={() => $assignSTMut.mutate({ subjectId: assigningSubjectId!, staffId: assignSTStaffId })}
          disabled={!assignSTStaffId || $assignSTMut.isPending}
          class="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:opacity-90">
          {$assignSTMut.isPending ? 'Saving…' : 'Assign'}
        </button>
      </div>
    </div>
  </div>
{/if}

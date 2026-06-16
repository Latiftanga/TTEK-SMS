<script lang="ts">
  import { writable } from 'svelte/store';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listClasses, updateClass, listProgrammes, type SchoolClass, type Programme } from '$lib/api/academic';
  import ClassCreateForm from './ClassCreateForm.svelte';
  import AssignSubjectsModal from './AssignSubjectsModal.svelte';

  const { selectedYearId, schoolType } = $props<{
    selectedYearId: string | null;
    schoolType: string;
  }>();

  const qc = useQueryClient();

  // Writable store so the Svelte 4 query API reacts when selectedYearId prop changes after mount.
  const classesOpts = writable({
    queryKey: ['classes', selectedYearId] as [string, string | null],
    queryFn: () => listClasses(selectedYearId!),
    enabled: !!selectedYearId, staleTime: 2 * 60_000,
  });
  $effect(() => classesOpts.set({
    queryKey: ['classes', selectedYearId],
    queryFn: () => listClasses(selectedYearId!),
    enabled: !!selectedYearId, staleTime: 2 * 60_000,
  }));
  const classesQuery = createQuery(classesOpts);

  // schoolType never changes mid-session — plain object is fine.
  const programmesQuery = createQuery({
    queryKey: ['programmes'],
    queryFn: listProgrammes,
    enabled: schoolType === 'SHS',
    staleTime: 5 * 60_000,
  });

  let editingClassId = $state<string | null>(null);
  let editForm = $state({ stream: '', capacity: '', programme_id: '' });
  let editError = $state('');

  const updateClassMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { stream?: string | null; capacity?: number | null; is_active?: boolean; programme_id?: string } }) =>
      updateClass(id, req),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['classes'] }); editingClassId = null; editError = ''; },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update class.';
    },
  });

  function startEditClass(cls: SchoolClass) {
    editingClassId = cls.id;
    editForm = { stream: cls.stream ?? '', capacity: cls.capacity?.toString() ?? '', programme_id: cls.programme_id ?? '' };
    editError = '';
  }

  function submitEditClass() {
    editError = '';
    $updateClassMut.mutate({
      id: editingClassId!,
      req: {
        stream: editForm.stream.trim() || null,
        capacity: editForm.capacity ? Number(editForm.capacity) : null,
        ...(schoolType === 'SHS' && editForm.programme_id ? { programme_id: editForm.programme_id } : {}),
      },
    });
  }

  let assigningClass = $state<{ id: string; name: string } | null>(null);
</script>

<div class="space-y-4">
  <ClassCreateForm {schoolType} {selectedYearId} programmes={$programmesQuery.data ?? []} />

  {#if $classesQuery.isPending}
    <div class="space-y-2">
      {#each [1,2,3,4] as _}
        <div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>
      {/each}
    </div>
  {:else if !selectedYearId}
    <p class="text-sm text-[var(--fg-muted)]">Select an academic year to view classes.</p>
  {:else if ($classesQuery.data ?? []).length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-7 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No classes for this year yet.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Class</th>
            {#if schoolType === 'SHS'}
              <th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Programme</th>
            {/if}
            <th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Capacity</th>
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each ($classesQuery.data ?? []).sort((a: SchoolClass, b: SchoolClass) => a.display_name.localeCompare(b.display_name)) as cls (cls.id)}
            {#if editingClassId === cls.id}
              <tr class="bg-[var(--bg)]">
                <td class="px-4 py-2 font-medium text-[var(--fg)]">{cls.display_name}</td>
                {#if schoolType === 'SHS'}
                  <td class="hidden px-4 py-2 sm:table-cell">
                    <select bind:value={editForm.programme_id}
                      class="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
                      <option value="">No programme</option>
                      {#each ($programmesQuery.data ?? []).filter((p: Programme) => p.is_active) as prog (prog.id)}
                        <option value={prog.id}>{prog.name}</option>
                      {/each}
                    </select>
                  </td>
                {/if}
                <td class="hidden px-3 py-2 sm:table-cell">
                  <input type="number" bind:value={editForm.capacity} placeholder="—"
                    class="w-20 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                </td>
                <td class="px-3 py-2">
                  <input bind:value={editForm.stream} placeholder="Stream"
                    class="w-24 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                  {#if editError}<p class="mt-1 text-[10px] text-red-500">{editError}</p>{/if}
                </td>
                <td class="px-3 py-2 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button onclick={submitEditClass} disabled={$updateClassMut.isPending}
                      class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
                      style="background-color: var(--brand)">
                      {$updateClassMut.isPending ? '…' : 'Save'}
                    </button>
                    <button onclick={() => { editingClassId = null; editError = ''; }}
                      class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--card)]">
                      Cancel
                    </button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr class="group transition hover:bg-[var(--bg)]">
                <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{cls.display_name}</td>
                {#if schoolType === 'SHS'}
                  <td class="hidden px-4 py-2.5 text-[var(--fg-muted)] sm:table-cell">{cls.programme_name ?? '—'}</td>
                {/if}
                <td class="hidden px-4 py-2.5 text-[var(--fg-muted)] sm:table-cell">{cls.capacity ?? '—'}</td>
                <td class="px-4 py-2.5">
                  <span class="badge {cls.is_active ? 'badge-success' : 'badge-neutral'}">
                    {cls.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td class="px-4 py-2.5 text-right">
                  <div class="flex items-center justify-end gap-1 opacity-0 transition group-hover:opacity-100">
                    <button onclick={() => startEditClass(cls)}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                      Edit
                    </button>
                    <button onclick={() => { assigningClass = { id: cls.id, name: cls.display_name }; }}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0118 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/></svg>
                      Subjects
                    </button>
                    <button onclick={() => $updateClassMut.mutate({ id: cls.id, req: { is_active: !cls.is_active } })}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium {cls.is_active ? 'text-red-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30' : 'text-green-500 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-950/30'}">
                      {#if cls.is_active}
                        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        Deactivate
                      {:else}
                        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        Activate
                      {/if}
                    </button>
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

{#if assigningClass}
  <AssignSubjectsModal
    classId={assigningClass.id}
    className={assigningClass.name}
    onclose={() => { assigningClass = null; }}
  />
{/if}

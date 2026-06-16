<script lang="ts">
  import { page } from '$app/stores';
  import { getContext } from 'svelte';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getClassTeacher, assignClassTeacher, type ClassTeacher, type AcademicTerm } from '$lib/api/academic';
  import { listStaff, type StaffSummary } from '$lib/api/staff';

  const classId = $derived($page.params.id);
  const termCtx = getContext<{ termId: string; terms: AcademicTerm[] }>('classTerm');
  const selectedTermId = $derived(termCtx.termId);

  const qc = useQueryClient();

  const classTchrQuery = createQuery(() => ({
    queryKey: ['class-teacher', classId, selectedTermId],
    queryFn: () => getClassTeacher(classId, selectedTermId),
    enabled: !!selectedTermId,
    staleTime: 60_000,
  }));
  const staffQuery = createQuery({ queryKey: ['staff'], queryFn: () => listStaff({ limit: 200 }), staleTime: 5 * 60_000 });

  const classTeacher = $derived<ClassTeacher | null>($classTchrQuery.data ?? null);
  const staff        = $derived<StaffSummary[]>($staffQuery.data ?? []);
  const staffMap     = $derived(new Map(staff.map(s => [s.id, s])));

  let showAssign      = $state(false);
  let assignStaffId   = $state('');
  let ctSearch        = $state('');
  const ctFiltered    = $derived(staff.filter(s => s.is_active && (!ctSearch || s.display_name.toLowerCase().includes(ctSearch.toLowerCase()))));

  const assignMut = createMutation({
    mutationFn: () => assignClassTeacher(classId, { staff_member_id: assignStaffId, academic_term_id: selectedTermId }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['class-teacher'] }); showAssign = false; assignStaffId = ''; },
  });

  function openAssign() { showAssign = true; assignStaffId = classTeacher?.staff_member_id ?? ''; ctSearch = ''; }
</script>

<div class="mb-3 flex items-center justify-between">
  <h2 class="text-base font-semibold text-[var(--fg)]">Class Teacher</h2>
  {#if selectedTermId}
    <button onclick={openAssign}
      class="h-8 rounded-lg border border-[var(--border)] px-3 text-xs font-medium text-[var(--fg)] hover:bg-[var(--hover)]">
      {classTeacher ? 'Change' : 'Assign'}
    </button>
  {/if}
</div>

{#if !selectedTermId}
  <p class="text-sm italic text-[var(--fg-muted)]">Select a term from the header to view and assign the class teacher.</p>
{:else if $classTchrQuery.isLoading}
  <p class="text-sm text-[var(--fg-muted)]">Loading…</p>
{:else if classTeacher}
  {@const teacher = staffMap.get(classTeacher.staff_member_id)}
  <div class="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
    <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--hover)] text-base font-bold text-[var(--fg)]">
      {(teacher?.display_name?.[0] ?? '?').toUpperCase()}
    </div>
    <div>
      <p class="font-medium text-[var(--fg)]">{teacher?.display_name ?? classTeacher.staff_member_id}</p>
      {#if teacher?.position_names?.length}
        <p class="text-xs text-[var(--fg-muted)]">{teacher.position_names.join(', ')}</p>
      {/if}
    </div>
  </div>
{:else}
  <div class="rounded-xl border border-dashed border-[var(--border)] py-12 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No class teacher assigned for this term.</p>
    <button onclick={openAssign} class="mt-2 text-sm text-[var(--brand)] hover:underline">
      Assign a class teacher
    </button>
  </div>
{/if}

{#if showAssign}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="mb-4 text-lg font-semibold text-[var(--fg)]">Assign Class Teacher</h2>
      <input bind:value={ctSearch} placeholder="Search staff…"
        class="mb-2 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]" />
      <div class="max-h-52 overflow-y-auto divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
        {#if ctFiltered.length === 0}
          <p class="px-3 py-4 text-center text-sm text-[var(--fg-muted)]">No staff found.</p>
        {:else}
          {#each ctFiltered as s}
            <button onclick={() => assignStaffId = s.id}
              class="w-full px-3 py-2 text-left text-sm hover:bg-[var(--hover)] {assignStaffId === s.id ? 'bg-[var(--hover)] font-medium' : ''}">
              {s.display_name}{s.position_names?.length ? ` · ${s.position_names.join(', ')}` : ''}
            </button>
          {/each}
        {/if}
      </div>
      <div class="mt-4 flex justify-end gap-3">
        <button onclick={() => showAssign = false} class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
        <button onclick={() => $assignMut.mutate()} disabled={!assignStaffId || $assignMut.isPending}
          class="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:opacity-90">
          {$assignMut.isPending ? 'Saving…' : 'Assign'}
        </button>
      </div>
    </div>
  </div>
{/if}

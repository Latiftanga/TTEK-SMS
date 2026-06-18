<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getClassTeacher, assignClassTeacher, type ClassTeacher } from '$lib/api/academic';
  import { listStaff, type StaffSummary } from '$lib/api/staff';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';

  interface Props { classId: string; selectedTermId: string; }
  const { classId, selectedTermId }: Props = $props();

  const qc = useQueryClient();

  const classTchrQuery = createQuery({
    queryKey: ['class-teacher', classId, selectedTermId],
    queryFn: () => getClassTeacher(classId, selectedTermId),
    enabled: !!selectedTermId,
    staleTime: 60_000,
  });
  const staffQuery = createQuery({ queryKey: ['staff'], queryFn: () => listStaff({ limit: 200 }), staleTime: 5 * 60_000 });

  const classTeacher = $derived<ClassTeacher | null>($classTchrQuery.data ?? null);
  const staff        = $derived<StaffSummary[]>($staffQuery.data ?? []);
  const staffMap     = $derived(new Map(staff.map(s => [s.id, s])));

  let showAssign      = $state(false);
  let assignStaffId   = $state('');
  let ctSearch        = $state('');
  const ctFiltered    = $derived(staff.filter(s => s.is_active && s.staff_category === 'TEACHING' && (!ctSearch || s.display_name.toLowerCase().includes(ctSearch.toLowerCase()))));

  const assignMut = createMutation({
    mutationFn: () => assignClassTeacher(classId, { staff_member_id: assignStaffId, academic_term_id: selectedTermId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-teacher'] });
      showAssign = false; assignStaffId = '';
      toast.success('Class teacher assigned.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to assign teacher. Check your permissions.';
      toast.error(msg);
    },
  });

  function openAssign() { showAssign = true; assignStaffId = classTeacher?.staff_member_id ?? ''; ctSearch = ''; }
</script>

<div class="mb-3 flex items-center justify-between">
  <p class="text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Class Teacher</p>
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
  <div class="skeleton h-20"></div>
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
  <EmptyState
    iconPath="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
    title="No class teacher assigned for this term."
    description="Assign a class teacher to manage attendance and student records."
    action={openAssign}
    actionLabel="Assign class teacher"
  />
{/if}

{#if showAssign}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
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

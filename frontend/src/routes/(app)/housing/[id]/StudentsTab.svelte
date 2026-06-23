<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getHouse, createAssignment, vacateAssignment } from '$lib/api/housing';
  import { listStudents } from '$lib/api/students';
  import { listYears } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props { houseId: string; canManage: boolean; }
  const { houseId, canManage }: Props = $props();

  const qc = useQueryClient();

  const houseQ    = createQuery({ queryKey: ['house', houseId],    queryFn: () => getHouse(houseId),   staleTime: 60_000 });
  const yearsQ    = createQuery({ queryKey: ['academic-years'],     queryFn: listYears,                  staleTime: 5 * 60_000 });
  const studentsQ = createQuery({ queryKey: ['students-boarding'],  queryFn: () => listStudents({ active_only: true }), staleTime: 5 * 60_000 });

  const currentYear = $derived(($yearsQ.data ?? []).find(y => y.is_current) ?? ($yearsQ.data ?? [])[0] ?? null);

  // ── Assignments in this house for current year ────────────────────────────────
  // We derive from students list — filter by house_id is not directly available,
  // so we show the assign form and let admins look up students.

  // ── Assign student ────────────────────────────────────────────────────────────
  let showAssign = $state(false);
  let af = $state({ student_id: '', room_id: '', assigned_at: new Date().toISOString().slice(0,10) });
  let afErr = $state('');
  let studentSearch = $state('');

  const filteredStudents = $derived(
    (($studentsQ.data ?? []).filter(s =>
      !studentSearch ||
      s.display_name.toLowerCase().includes(studentSearch.toLowerCase()) ||
      s.admission_number.toLowerCase().includes(studentSearch.toLowerCase())
    )).slice(0, 20)
  );

  const assignMut = createMutation({
    mutationFn: () => createAssignment({
      student_id: af.student_id,
      house_id: houseId,
      room_id: af.room_id || undefined,
      academic_year_id: currentYear!.id,
      assigned_at: af.assigned_at,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house', houseId] });
      showAssign = false;
      af = { student_id: '', room_id: '', assigned_at: new Date().toISOString().slice(0,10) };
      studentSearch = '';
      toast.success('Student assigned to house.');
    },
    onError: (e: unknown) => {
      afErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not assign student.';
    },
  });

  function handleAssign() {
    afErr = '';
    if (!af.student_id) { afErr = 'Select a student.'; return; }
    if (!currentYear) { afErr = 'No current academic year found.'; return; }
    $assignMut.mutate();
  }

  // ── Vacate ────────────────────────────────────────────────────────────────────
  let vacateId = $state<string | null>(null);
  let vacateDate = $state(new Date().toISOString().slice(0,10));

  const vacateMut = createMutation({
    mutationFn: () => vacateAssignment(vacateId!, vacateDate),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house', houseId] });
      vacateId = null;
      toast.success('Student vacated.');
    },
    onError: () => toast.error('Could not vacate assignment.'),
  });

  const rooms = $derived($houseQ.data?.rooms ?? []);
  const roomName = (id: string | null) => rooms.find(r => r.id === id)?.room_number ?? '—';
</script>

<div>
  {#if canManage}
    <div class="mb-3 flex justify-end">
      <button onclick={() => { showAssign = !showAssign; afErr = ''; }}
        class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Assign student
      </button>
    </div>
  {/if}

  {#if showAssign}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p class="mb-3 text-sm font-semibold text-[var(--fg)]">Assign student to this house</p>
      {#if currentYear}
        <p class="mb-3 text-xs text-[var(--fg-muted)]">Academic year: <span class="font-medium">{currentYear.name}</span></p>
      {/if}
      <div class="grid gap-3 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="label">Search student <span class="text-red-500">*</span></label>
          <input bind:value={studentSearch} placeholder="Name or admission number…" class="input mb-1" />
          {#if studentSearch}
            <div class="max-h-40 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg)]">
              {#each filteredStudents as s (s.id)}
                <button onclick={() => { af.student_id = s.id; studentSearch = `${s.display_name} (${s.admission_number})`; }}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--hover)] transition
                         {af.student_id === s.id ? 'bg-[var(--hover)] font-medium' : ''}">
                  <span class="font-medium text-[var(--fg)]">{s.display_name}</span>
                  <span class="text-xs text-[var(--fg-muted)]">{s.admission_number}</span>
                </button>
              {:else}
                <p class="px-3 py-2 text-xs text-[var(--fg-muted)]">No students found.</p>
              {/each}
            </div>
          {/if}
        </div>
        <div>
          <label class="label">Room (optional)</label>
          <select bind:value={af.room_id} class="input">
            <option value="">No specific room</option>
            {#each rooms as r}<option value={r.id}>{r.room_number} ({r.room_type})</option>{/each}
          </select>
        </div>
        <div>
          <label class="label">Assigned from <span class="text-red-500">*</span></label>
          <input type="date" bind:value={af.assigned_at} class="input" />
        </div>
      </div>
      {#if afErr}<p class="mt-2 text-xs text-red-500">{afErr}</p>{/if}
      <div class="mt-3 flex gap-2">
        <button onclick={handleAssign} disabled={$assignMut.isPending}
          class="rounded-xl px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background:var(--brand)">
          {$assignMut.isPending ? 'Assigning…' : 'Assign'}
        </button>
        <button onclick={() => { showAssign = false; afErr = ''; }}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Vacate modal -->
  {#if vacateId}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
        <p class="mb-3 font-semibold text-[var(--fg)]">Record departure</p>
        <label class="label">Vacated on</label>
        <input type="date" bind:value={vacateDate} class="input mb-4" />
        <div class="flex gap-2">
          <button onclick={() => $vacateMut.mutate()} disabled={$vacateMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background:var(--brand)">
            {$vacateMut.isPending ? 'Saving…' : 'Confirm'}
          </button>
          <button onclick={() => vacateId = null}
            class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      </div>
    </div>
  {/if}

  <p class="mb-3 text-xs text-[var(--fg-muted)]">Showing active assignments for the current academic year.</p>

  <div class="rounded-2xl border border-dashed border-[var(--border)] p-8 text-center">
    <p class="text-sm text-[var(--fg-muted)]">
      To see all students in this house, use the Students module and filter by housing.
    </p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">
      Use "Assign student" to place a boarder in this house.
    </p>
  </div>
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>

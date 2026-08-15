<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listHouseStudents, createAssignment, vacateAssignment } from '$lib/api/housing';
  import { listStudents } from '$lib/api/students';
  import { getHouse } from '$lib/api/housing';
  import { listYears } from '$lib/api/academic';
  import { findCurrentYear } from '$lib/academicPeriod';
  import { toast } from '$lib/stores/toast';

  interface Props { houseId: string; canManage: boolean; }
  const { houseId, canManage }: Props = $props();

  const qc = useQueryClient();

  const residentsQ = createQuery({
    queryKey: ['house-students', houseId],
    queryFn:  () => listHouseStudents(houseId),
    staleTime: 60_000,
  });
  const houseQ    = createQuery({ queryKey: ['house', houseId], queryFn: () => getHouse(houseId), staleTime: 2 * 60_000 });
  const yearsQ    = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const studentsQ = createQuery({ queryKey: ['students-all'],   queryFn: () => listStudents({ active_only: true }), staleTime: 5 * 60_000 });

  // No fallback to an unsorted-order year here — this assigns a real
  // record, same stance as AssignStudentsPanel.svelte; the guard in
  // handleAssign() below is reachable now that this never guesses.
  const currentYear = $derived(findCurrentYear($yearsQ.data ?? []) ?? null);
  const rooms       = $derived($houseQ.data?.rooms ?? []);

  // ── Assign ────────────────────────────────────────────────────────────────────
  let showAssign  = $state(false);
  let af          = $state({ student_id: '', room_id: '', assigned_at: new Date().toISOString().slice(0,10) });
  let afErr       = $state('');
  let studentSearch = $state('');

  const filteredStudents = $derived(
    (($studentsQ.data ?? []).filter(s =>
      !studentSearch ||
      s.display_name.toLowerCase().includes(studentSearch.toLowerCase()) ||
      s.admission_number.toLowerCase().includes(studentSearch.toLowerCase())
    )).slice(0, 20)
  );

  const assignMut = createMutation({
    mutationFn: (academicYearId: string) => createAssignment({
      student_id: af.student_id, house_id: houseId,
      room_id: af.room_id || undefined,
      academic_year_id: academicYearId, assigned_at: af.assigned_at,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house-students', houseId] });
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
    if (!currentYear)   { afErr = 'No current academic year found.'; return; }
    $assignMut.mutate(currentYear.id);
  }

  // ── Vacate ────────────────────────────────────────────────────────────────────
  let vacateId   = $state<string | null>(null);
  let vacateName = $state('');
  let vacateDate = $state(new Date().toISOString().slice(0,10));

  const vacateMut = createMutation({
    mutationFn: () => vacateAssignment(vacateId!, vacateDate),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house-students', houseId] });
      vacateId = null;
      toast.success('Student departure recorded.');
    },
    onError: () => toast.error('Could not record departure.'),
  });

  const GENDER_LABEL: Record<string, string> = { MALE: 'M', FEMALE: 'F' };
</script>

<!-- Vacate modal -->
{#if vacateId}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
      <p class="mb-1 font-semibold text-[var(--fg)]">Record departure</p>
      <p class="mb-4 text-xs text-[var(--fg-muted)]">{vacateName}</p>
      <label class="label">Departed on</label>
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

{#if canManage}
  <div class="mb-4 flex justify-end">
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
        <label class="label">Student <span class="text-red-500">*</span></label>
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

{#if $residentsQ.isPending}
  <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if ($residentsQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No students currently assigned to this house.</p>
    {#if canManage}<p class="mt-1 text-xs text-[var(--fg-subtle)]">Use "Assign student" to add a boarder.</p>{/if}
  </div>
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <p class="border-b border-[var(--border)] px-4 py-2 text-xs font-semibold text-[var(--fg-subtle)]">
      {$residentsQ.data!.length} resident{$residentsQ.data!.length === 1 ? '' : 's'}
    </p>
    <table class="w-full text-sm">
      <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-3">Name</th>
        <th class="hidden px-4 py-3 sm:table-cell">Admission No.</th>
        <th class="hidden px-4 py-3 sm:table-cell">Room</th>
        <th class="hidden px-4 py-3 md:table-cell">Since</th>
        {#if canManage}<th class="px-4 py-3"></th>{/if}
      </tr></thead>
      <tbody>
        {#each $residentsQ.data ?? [] as s (s.assignment_id)}
          <tr class="border-b border-[var(--border)] last:border-0">
            <td class="px-4 py-3">
              <p class="font-medium text-[var(--fg)]">{s.student_name}</p>
              {#if s.gender}
                <span class="text-[10px] text-[var(--fg-subtle)]">{GENDER_LABEL[s.gender] ?? s.gender}</span>
              {/if}
            </td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{s.admission_number}</td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{s.room_number ?? '—'}</td>
            <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{s.assigned_at}</td>
            {#if canManage}
              <td class="px-4 py-3 text-right">
                <button onclick={() => { vacateId = s.assignment_id; vacateName = s.student_name; vacateDate = new Date().toISOString().slice(0,10); }}
                  class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-semibold
                         text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
                  Departed
                </button>
              </td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>

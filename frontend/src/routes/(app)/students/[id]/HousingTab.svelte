<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listYears } from '$lib/api/academic';
  import {
    listHouses, getStudentAssignment, createAssignment, vacateAssignment,
    listStudentExeats, createExeat,
  } from '$lib/api/housing';
  import { toast } from '$lib/stores/toast';

  interface Props { studentId: string; isBoarding: boolean; }
  const { studentId, isBoarding }: Props = $props();

  const qc = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);

  // ── Years (shared cache) ──────────────────────────────────────────────────────
  const yearsQ = createQuery({
    queryKey: ['academic-years'],
    queryFn: listYears,
    staleTime: 5 * 60_000,
    enabled: isBoarding,
  });

  let selectedYearId = $state('');
  $effect(() => {
    const years = $yearsQ.data ?? [];
    if (!selectedYearId && years.length)
      selectedYearId = years.find(y => y.is_current)?.id ?? years[0]?.id ?? '';
  });

  // ── Houses (for assignment picker) ────────────────────────────────────────────
  const housesQ = createQuery({
    queryKey: ['houses'],
    queryFn: listHouses,
    enabled: isBoarding,
    staleTime: 5 * 60_000,
  });

  const houseMap = $derived(new Map(($housesQ.data ?? []).map(h => [h.id, h])));

  // ── Current assignment ────────────────────────────────────────────────────────
  const assignmentQ = createQuery({
    queryKey: () => ['student-assignment', studentId, selectedYearId],
    queryFn: () => getStudentAssignment(studentId, selectedYearId),
    enabled: () => !!selectedYearId && isBoarding,
    staleTime: 60_000,
  });

  const assignment   = $derived($assignmentQ.data ?? null);
  const assignedHouse = $derived(assignment ? houseMap.get(assignment.house_id) : null);
  const assignedRoom  = $derived(
    assignment?.room_id && assignedHouse
      ? assignedHouse.rooms.find(r => r.id === assignment.room_id)
      : null
  );

  // ── Assign form ───────────────────────────────────────────────────────────────
  let showAssignForm = $state(false);
  let aHouseId  = $state('');
  let aRoomId   = $state('');
  let aDate     = $state(today);
  let aError    = $state('');

  const pickedRooms = $derived(aHouseId ? (houseMap.get(aHouseId)?.rooms ?? []) : []);
  $effect(() => { if (aHouseId) aRoomId = ''; });

  const assignMut = createMutation({
    mutationFn: () => createAssignment({
      student_id: studentId, house_id: aHouseId,
      room_id: aRoomId || null, academic_year_id: selectedYearId, assigned_at: aDate,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-assignment', studentId] });
      showAssignForm = false; aHouseId = ''; aRoomId = ''; aError = '';
      toast.success('House assigned.');
    },
    onError: (e: unknown) => {
      aError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not assign house.';
    },
  });

  const vacateMut = createMutation({
    mutationFn: () => vacateAssignment(assignment!.id, today),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-assignment', studentId] });
      toast.success('Student vacated from house.');
    },
    onError: () => toast.error('Could not vacate.'),
  });

  // ── Exeats ────────────────────────────────────────────────────────────────────
  const exeatsQ = createQuery({
    queryKey: ['student-exeats', studentId],
    queryFn: () => listStudentExeats(studentId),
    enabled: isBoarding,
    staleTime: 60_000,
  });

  let showExeatForm = $state(false);
  let eReason  = $state('');
  let eDest    = $state('');
  let eDep     = $state('');
  let eReturn  = $state('');
  let eError   = $state('');

  const exeatMut = createMutation({
    mutationFn: () => createExeat({
      student_id: studentId, reason: eReason, destination: eDest,
      departure_date: eDep, return_date: eReturn,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-exeats', studentId] });
      showExeatForm = false; eReason = ''; eDest = ''; eDep = ''; eReturn = ''; eError = '';
      toast.success('Exeat request created.');
    },
    onError: (e: unknown) => {
      eError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not create exeat.';
    },
  });

  const STATUS: Record<string, { label: string; cls: string }> = {
    PENDING: { label: 'Pending', cls: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300' },
    APPROVED: { label: 'Approved', cls: 'bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-400' },
    REJECTED: { label: 'Rejected', cls: 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400' },
  };
</script>

{#if !isBoarding}
  <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 text-center">
    <svg class="mx-auto mb-2 h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75"/>
    </svg>
    <p class="text-sm font-medium text-[var(--fg)]">Not a boarding student</p>
    <p class="mt-1 text-xs text-[var(--fg-muted)]">Mark as boarder in the Profile tab to manage housing.</p>
  </div>

{:else}
  <div class="space-y-5">
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-5 py-3.5">
        <h2 class="text-sm font-semibold text-[var(--fg)]">House Assignment</h2>
        {#if $yearsQ.data && $yearsQ.data.length > 1}
          <select bind:value={selectedYearId}
            class="rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5 text-xs text-[var(--fg)]
                   focus:border-[var(--brand)] focus:outline-none">
            {#each $yearsQ.data as y}
              <option value={y.id}>{y.name}</option>
            {/each}
          </select>
        {/if}
      </div>

      <div class="p-5">
        {#if $assignmentQ.isPending || $housesQ.isPending}
          <div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>
        {:else if assignment && assignedHouse}
          {#if !assignment.vacated_at}
            <div class="flex items-center gap-4">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white"
                   style="background-color: {assignedHouse.color ?? 'var(--brand)'}">
                {assignedHouse.code.slice(0, 2)}
              </div>
              <div class="min-w-0 flex-1">
                <p class="font-semibold text-[var(--fg)]">{assignedHouse.name}</p>
                <p class="text-xs text-[var(--fg-muted)]">
                  {assignedRoom ? `Room ${assignedRoom.room_number}` : 'No room specified'}
                  · Since {assignment.assigned_at}
                </p>
              </div>
              <button onclick={() => $vacateMut.mutate()} disabled={$vacateMut.isPending}
                class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium
                       text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                {$vacateMut.isPending ? '…' : 'Vacate'}
              </button>
            </div>
          {:else}
            <div class="rounded-xl bg-[var(--hover)] p-4 text-sm text-[var(--fg-muted)]">
              Previously in {assignedHouse.name} · vacated {assignment.vacated_at}
            </div>
            {#if !showAssignForm}
              <button onclick={() => showAssignForm = true} class="mt-3 text-xs font-semibold" style="color: var(--brand)">
                + Assign to a house
              </button>
            {/if}
          {/if}
        {:else}
          <p class="mb-3 text-sm text-[var(--fg-muted)]">Not assigned to a house this year.</p>
          {#if !showAssignForm}
            <button onclick={() => showAssignForm = true} class="btn-primary text-xs">Assign to house</button>
          {/if}
        {/if}

        {#if showAssignForm}
          <div class="mt-4 space-y-3 rounded-xl border border-[var(--border)] p-4">
            <p class="text-xs font-medium text-[var(--fg-muted)]">Assign to house</p>
            <div class="grid gap-2 sm:grid-cols-2">
              <select bind:value={aHouseId} class="sel">
                <option value="">Select house…</option>
                {#each $housesQ.data ?? [] as h}
                  <option value={h.id}>{h.name}</option>
                {/each}
              </select>
              <select bind:value={aRoomId} class="sel" disabled={pickedRooms.length === 0}>
                <option value="">Room (optional)</option>
                {#each pickedRooms as r}
                  <option value={r.id}>Room {r.room_number}</option>
                {/each}
              </select>
              <div class="sm:col-span-2">
                <label class="mb-1 block text-xs text-[var(--fg-muted)]">Date assigned</label>
                <input type="date" bind:value={aDate} class="sel" />
              </div>
            </div>
            {#if aError}<p class="text-xs text-red-500">{aError}</p>{/if}
            <div class="flex gap-2">
              <button onclick={() => $assignMut.mutate()} disabled={!aHouseId || $assignMut.isPending} class="btn-primary text-xs">
                {$assignMut.isPending ? 'Assigning…' : 'Assign'}
              </button>
              <button onclick={() => { showAssignForm = false; aError = ''; }} class="btn-ghost text-xs">Cancel</button>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-5 py-3.5">
        <h2 class="text-sm font-semibold text-[var(--fg)]">Exeats</h2>
        {#if !showExeatForm}
          <button onclick={() => showExeatForm = true} class="btn-ghost text-xs">+ Request</button>
        {/if}
      </div>

      <div class="p-5">
        {#if showExeatForm}
          <div class="mb-4 space-y-3 rounded-xl border border-[var(--border)] p-4">
            <p class="text-xs font-medium text-[var(--fg-muted)]">New exeat request</p>
            <div class="grid gap-2 sm:grid-cols-2">
              <div class="sm:col-span-2"><label class="mb-1 block text-xs text-[var(--fg-muted)]">Reason</label><input bind:value={eReason} placeholder="e.g. Family visit" class="sel" /></div>
              <div class="sm:col-span-2"><label class="mb-1 block text-xs text-[var(--fg-muted)]">Destination</label><input bind:value={eDest} placeholder="e.g. Home, Accra" class="sel" /></div>
              <div><label class="mb-1 block text-xs text-[var(--fg-muted)]">Departure</label><input type="date" bind:value={eDep} class="sel" /></div>
              <div><label class="mb-1 block text-xs text-[var(--fg-muted)]">Return date</label><input type="date" bind:value={eReturn} class="sel" /></div>
            </div>
            {#if eError}<p class="text-xs text-red-500">{eError}</p>{/if}
            <div class="flex gap-2">
              <button onclick={() => $exeatMut.mutate()}
                disabled={!eReason || !eDest || !eDep || !eReturn || $exeatMut.isPending}
                class="btn-primary text-xs">
                {$exeatMut.isPending ? 'Creating…' : 'Create request'}
              </button>
              <button onclick={() => { showExeatForm = false; eError = ''; }} class="btn-ghost text-xs">Cancel</button>
            </div>
          </div>
        {/if}

        {#if $exeatsQ.isPending}
          <div class="space-y-2">{#each [1,2] as _}<div class="h-10 animate-pulse rounded-lg bg-[var(--hover)]"></div>{/each}</div>
        {:else if ($exeatsQ.data ?? []).length === 0}
          <p class="text-sm text-[var(--fg-muted)]">No exeat requests yet.</p>
        {:else}
          <div class="divide-y divide-[var(--border)]">
            {#each $exeatsQ.data ?? [] as exeat (exeat.id)}
              {@const s = STATUS[exeat.status]}
              <div class="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <div class="min-w-0">
                  <p class="text-sm font-medium text-[var(--fg)]">{exeat.destination}</p>
                  <p class="text-xs text-[var(--fg-muted)]">
                    {exeat.departure_date} → {exeat.return_date}
                    {#if exeat.reason} · {exeat.reason}{/if}
                  </p>
                  {#if exeat.actual_return_date}
                    <p class="text-xs text-[var(--fg-muted)]">Returned: {exeat.actual_return_date}</p>
                  {/if}
                </div>
                <span class="shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold {s.cls}">{s.label}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

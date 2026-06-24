<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listHouseExeats, approveExeat, recordReturn, createExeat,
    type ExeatRead, type ExeatType,
  } from '$lib/api/housing';
  import { listStudents } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';
  import ExeatsTable from '../ExeatsTable.svelte';

  interface Props { houseId: string; canManage: boolean; }
  const { houseId, canManage }: Props = $props();

  const qc = useQueryClient();

  const exeatsQ   = createQuery({ queryKey: ['exeats', houseId], queryFn: () => listHouseExeats(houseId), staleTime: 60_000 });
  const studentsQ = createQuery({ queryKey: ['students-boarding'], queryFn: () => listStudents({ active_only: true }), staleTime: 5 * 60_000 });

  const pendingExternal  = $derived<ExeatRead[]>(($exeatsQ.data ?? []).filter(e => e.status === 'PENDING'  && e.exeat_type === 'EXTERNAL'));
  const pendingInternal  = $derived<ExeatRead[]>(($exeatsQ.data ?? []).filter(e => e.status === 'PENDING'  && e.exeat_type === 'INTERNAL'));
  const approvedExternal = $derived<ExeatRead[]>(($exeatsQ.data ?? []).filter(e => e.status === 'APPROVED' && e.exeat_type === 'EXTERNAL'));
  const approvedInternal = $derived<ExeatRead[]>(($exeatsQ.data ?? []).filter(e => e.status === 'APPROVED' && e.exeat_type === 'INTERNAL'));

  // ── Review ────────────────────────────────────────────────────────────────────
  const reviewMut = createMutation({
    mutationFn: ({ id, status }: { id: string; status: 'APPROVED' | 'REJECTED' }) => approveExeat(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['exeats', houseId] }); toast.success('Exeat updated.'); },
    onError: () => toast.error('Could not update exeat.'),
  });

  // ── Record return ─────────────────────────────────────────────────────────────
  let returningId = $state<string | null>(null);
  let returnDate  = $state(new Date().toISOString().slice(0,10));

  const returnMut = createMutation({
    mutationFn: () => recordReturn(returningId!, returnDate),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exeats', houseId] });
      returningId = null;
      toast.success('Return recorded.');
    },
    onError: () => toast.error('Could not record return.'),
  });

  function openReturn(id: string) { returningId = id; returnDate = new Date().toISOString().slice(0,10); }

  // ── New exeat form ────────────────────────────────────────────────────────────
  let showForm = $state(false);
  let ef = $state({
    student_id: '', studentSearch: '', exeat_type: 'EXTERNAL' as ExeatType,
    reason: '', destination: '', departure_date: '', return_date: '',
  });
  let efErr = $state('');

  const filteredStudents = $derived(
    (($studentsQ.data ?? []).filter(s =>
      !ef.studentSearch ||
      s.display_name.toLowerCase().includes(ef.studentSearch.toLowerCase()) ||
      s.admission_number.toLowerCase().includes(ef.studentSearch.toLowerCase())
    )).slice(0, 20)
  );

  const createMut = createMutation({
    mutationFn: () => createExeat({
      student_id: ef.student_id, exeat_type: ef.exeat_type,
      reason: ef.reason.trim(), destination: ef.destination.trim(),
      departure_date: ef.departure_date, return_date: ef.return_date,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exeats', houseId] });
      showForm = false;
      ef = { student_id: '', studentSearch: '', exeat_type: 'EXTERNAL', reason: '', destination: '', departure_date: '', return_date: '' };
      toast.success('Exeat created.');
    },
    onError: (e: unknown) => {
      efErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create exeat.';
    },
  });

  function handleCreate() {
    efErr = '';
    if (!ef.student_id)         { efErr = 'Select a student.'; return; }
    if (!ef.reason.trim())      { efErr = 'Reason is required.'; return; }
    if (!ef.destination.trim()) { efErr = 'Destination / location is required.'; return; }
    if (!ef.departure_date)     { efErr = 'Departure date is required.'; return; }
    if (!ef.return_date)        { efErr = 'Return date is required.'; return; }
    if (ef.return_date < ef.departure_date) { efErr = 'Return date must be on or after departure.'; return; }
    $createMut.mutate();
  }
</script>

<!-- Return date modal -->
{#if returningId}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
      <p class="mb-1 font-semibold text-[var(--fg)]">Record return</p>
      <p class="mb-4 text-xs text-[var(--fg-muted)]">Enter the actual date the student returned.</p>
      <label class="label">Return date</label>
      <input type="date" bind:value={returnDate} class="input mb-4" />
      <div class="flex gap-2">
        <button onclick={() => $returnMut.mutate()} disabled={$returnMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$returnMut.isPending ? 'Saving…' : 'Confirm return'}
        </button>
        <button onclick={() => returningId = null}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Issue exeat button -->
{#if canManage}
  <div class="mb-5 flex justify-end">
    <button onclick={() => { showForm = !showForm; efErr = ''; }}
      class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Issue exeat
    </button>
  </div>

  {#if showForm}
    <div class="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <p class="mb-3 text-sm font-semibold text-[var(--fg)]">Issue exeat</p>

      <div class="mb-4 flex gap-2">
        {#each (['EXTERNAL', 'INTERNAL'] as ExeatType[]) as t}
          <button onclick={() => ef.exeat_type = t}
            class="flex-1 rounded-xl border py-2 text-sm font-medium transition
                   {ef.exeat_type === t
                     ? t === 'EXTERNAL'
                       ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400'
                       : 'border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                     : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
            {t === 'EXTERNAL' ? 'External — travels out of town/city' : 'Internal — stays within town/locality'}
          </button>
        {/each}
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="label">Student <span class="text-red-500">*</span></label>
          <input bind:value={ef.studentSearch} placeholder="Search by name or admission number…" class="input mb-1"
            oninput={() => { ef.student_id = ''; }} />
          {#if ef.studentSearch && !ef.student_id}
            <div class="max-h-40 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg)]">
              {#each filteredStudents as s (s.id)}
                <button onclick={() => { ef.student_id = s.id; ef.studentSearch = `${s.display_name} (${s.admission_number})`; }}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--hover)] transition">
                  <span class="font-medium text-[var(--fg)]">{s.display_name}</span>
                  <span class="text-xs text-[var(--fg-muted)]">{s.admission_number}</span>
                </button>
              {:else}
                <p class="px-3 py-2 text-xs text-[var(--fg-muted)]">No students found.</p>
              {/each}
            </div>
          {/if}
        </div>
        <div class="sm:col-span-2">
          <label class="label">Reason <span class="text-red-500">*</span></label>
          <input bind:value={ef.reason} placeholder="e.g. Family funeral, medical appointment…" class="input" />
        </div>
        <div class="sm:col-span-2">
          <label class="label">
            Destination
            <span class="text-red-500">*</span>
          </label>
          <input bind:value={ef.destination}
            placeholder={ef.exeat_type === 'EXTERNAL' ? 'e.g. Accra, Kumasi…' : 'e.g. Town clinic, Local market…'}
            class="input" />
        </div>
        <div>
          <label class="label">Departure date <span class="text-red-500">*</span></label>
          <input type="date" bind:value={ef.departure_date} class="input" />
        </div>
        <div>
          <label class="label">Return date <span class="text-red-500">*</span></label>
          <input type="date" bind:value={ef.return_date} class="input" />
        </div>
      </div>
      {#if efErr}<p class="mt-2 text-xs text-red-500">{efErr}</p>{/if}
      <div class="mt-3 flex gap-2">
        <button onclick={handleCreate} disabled={$createMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$createMut.isPending ? 'Issuing…' : 'Issue exeat'}
        </button>
        <button onclick={() => { showForm = false; efErr = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  {/if}
{/if}

{#if $exeatsQ.isPending}
  <div class="space-y-3">{#each [1,2] as _}<div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>
{:else}
  <ExeatsTable
    dotColor="bg-blue-500"
    heading="External exeats"
    pending={pendingExternal}
    approved={approvedExternal}
    approvedLabel="Off campus"
    destinationHeader="Destination"
    actionPending={$reviewMut.isPending}
    onApprove={id => $reviewMut.mutate({ id, status: 'APPROVED' })}
    onReject={id => $reviewMut.mutate({ id, status: 'REJECTED' })}
    onReturn={openReturn}
  />

  <ExeatsTable
    dotColor="bg-amber-500"
    heading="Internal exeats"
    pending={pendingInternal}
    approved={approvedInternal}
    approvedLabel="Approved — in locality"
    destinationHeader="Destination"
    actionPending={$reviewMut.isPending}
    onApprove={id => $reviewMut.mutate({ id, status: 'APPROVED' })}
    onReject={id => $reviewMut.mutate({ id, status: 'REJECTED' })}
    onReturn={openReturn}
  />
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>

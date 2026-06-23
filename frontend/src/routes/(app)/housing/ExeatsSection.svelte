<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listPendingExeats, approveExeat, recordReturn, createExeat, type ExeatRead } from '$lib/api/housing';
  import { listStudents } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';

  interface Props { canManage: boolean; }
  const { canManage }: Props = $props();

  const qc = useQueryClient();

  const exeatsQ   = createQuery({ queryKey: ['exeats-pending'],   queryFn: listPendingExeats, staleTime: 60_000 });
  const studentsQ = createQuery({ queryKey: ['students-boarding'], queryFn: () => listStudents({ active_only: true }), staleTime: 5 * 60_000 });

  const pending  = $derived<ExeatRead[]>(($exeatsQ.data ?? []).filter(e => e.status === 'PENDING'));
  const offCampus = $derived<ExeatRead[]>(($exeatsQ.data ?? []).filter(e => e.status === 'APPROVED'));

  // ── Review ────────────────────────────────────────────────────────────────────
  const reviewMut = createMutation({
    mutationFn: ({ id, status }: { id: string; status: 'APPROVED' | 'REJECTED' }) => approveExeat(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['exeats-pending'] }); toast.success('Exeat updated.'); },
    onError: () => toast.error('Could not update exeat.'),
  });

  // ── Record return with date picker ────────────────────────────────────────────
  let returningId   = $state<string | null>(null);
  let returnDate    = $state(new Date().toISOString().slice(0,10));

  const returnMut = createMutation({
    mutationFn: () => recordReturn(returningId!, returnDate),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exeats-pending'] });
      returningId = null;
      toast.success('Return recorded.');
    },
    onError: () => toast.error('Could not record return.'),
  });

  // ── New exeat ─────────────────────────────────────────────────────────────────
  let showForm = $state(false);
  let ef = $state({ student_id: '', studentSearch: '', reason: '', destination: '', departure_date: '', return_date: '' });
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
      student_id: ef.student_id, reason: ef.reason.trim(),
      destination: ef.destination.trim(),
      departure_date: ef.departure_date, return_date: ef.return_date,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exeats-pending'] });
      showForm = false;
      ef = { student_id: '', studentSearch: '', reason: '', destination: '', departure_date: '', return_date: '' };
      toast.success('Exeat request created.');
    },
    onError: (e: unknown) => {
      efErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create exeat.';
    },
  });

  function handleCreate() {
    efErr = '';
    if (!ef.student_id)         { efErr = 'Select a student.'; return; }
    if (!ef.reason.trim())      { efErr = 'Reason is required.'; return; }
    if (!ef.destination.trim()) { efErr = 'Destination is required.'; return; }
    if (!ef.departure_date)     { efErr = 'Departure date is required.'; return; }
    if (!ef.return_date)        { efErr = 'Return date is required.'; return; }
    if (ef.return_date < ef.departure_date) { efErr = 'Return date must be on or after departure date.'; return; }
    $createMut.mutate();
  }
</script>

<!-- Return date modal -->
{#if returningId}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl">
      <p class="mb-1 font-semibold text-[var(--fg)]">Record return</p>
      <p class="mb-4 text-xs text-[var(--fg-muted)]">Enter the actual date the student returned to campus.</p>
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

<!-- ── Pending exeats ─────────────────────────────────────────────────────────── -->
<div class="mb-6">
  <div class="mb-3 flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">
      Pending exeats
      {#if pending.length > 0}
        <span class="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700
                     dark:bg-amber-900/40 dark:text-amber-400">{pending.length}</span>
      {/if}
    </p>
    {#if canManage}
      <button onclick={() => { showForm = !showForm; efErr = ''; }}
        class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        New exeat
      </button>
    {/if}
  </div>

  {#if showForm}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <p class="mb-3 text-sm font-semibold text-[var(--fg)]">New exeat request</p>
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
          <label class="label">Destination <span class="text-red-500">*</span></label>
          <input bind:value={ef.destination} placeholder="e.g. Accra, Kumasi…" class="input" />
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
          {$createMut.isPending ? 'Creating…' : 'Create exeat'}
        </button>
        <button onclick={() => { showForm = false; efErr = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if $exeatsQ.isPending}
    <div class="space-y-2">{#each [1,2] as _}<div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>
  {:else if pending.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-6 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No pending exeats.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Student</th>
          <th class="hidden px-4 py-3 sm:table-cell">Reason</th>
          <th class="hidden px-4 py-3 md:table-cell">Destination</th>
          <th class="hidden px-4 py-3 md:table-cell">Departs</th>
          <th class="hidden px-4 py-3 md:table-cell">Returns</th>
          <th class="px-4 py-3">Actions</th>
        </tr></thead>
        <tbody>
          {#each pending as e (e.id)}
            <tr class="border-b border-[var(--border)] last:border-0">
              <td class="px-4 py-3">
                <p class="font-medium text-[var(--fg)]">{e.student_name ?? '—'}</p>
                <p class="text-[10px] text-[var(--fg-subtle)]">{e.admission_number ?? ''}</p>
              </td>
              <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] sm:table-cell max-w-[160px] truncate">{e.reason}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{e.destination}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{e.departure_date}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{e.return_date}</td>
              <td class="px-4 py-3">
                <div class="flex gap-2">
                  <button onclick={() => $reviewMut.mutate({ id: e.id, status: 'APPROVED' })}
                    disabled={$reviewMut.isPending}
                    class="rounded-lg bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-700 transition
                           hover:bg-green-100 dark:bg-green-950/40 dark:text-green-400 disabled:opacity-50">
                    Approve
                  </button>
                  <button onclick={() => $reviewMut.mutate({ id: e.id, status: 'REJECTED' })}
                    disabled={$reviewMut.isPending}
                    class="rounded-lg bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 transition
                           hover:bg-red-100 dark:bg-red-950/40 dark:text-red-400 disabled:opacity-50">
                    Reject
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- ── Off-campus (approved) ──────────────────────────────────────────────────── -->
<div>
  <p class="mb-3 text-sm font-semibold text-[var(--fg)]">
    Off campus
    {#if offCampus.length > 0}
      <span class="ml-1.5 rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-700
                   dark:bg-blue-950/40 dark:text-blue-400">{offCampus.length}</span>
    {/if}
  </p>

  {#if $exeatsQ.isPending}
    <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  {:else if offCampus.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-6 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No students currently off campus.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Student</th>
          <th class="hidden px-4 py-3 sm:table-cell">Destination</th>
          <th class="hidden px-4 py-3 sm:table-cell">Departed</th>
          <th class="px-4 py-3">Expected back</th>
          <th class="px-4 py-3"></th>
        </tr></thead>
        <tbody>
          {#each offCampus as e (e.id)}
            {@const overdue = e.return_date < new Date().toISOString().slice(0,10)}
            <tr class="border-b border-[var(--border)] last:border-0 {overdue ? 'bg-red-50/50 dark:bg-red-950/10' : ''}">
              <td class="px-4 py-3">
                <p class="font-medium text-[var(--fg)]">{e.student_name ?? '—'}</p>
                <p class="text-[10px] text-[var(--fg-subtle)]">{e.admission_number ?? ''}</p>
              </td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.destination}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.departure_date}</td>
              <td class="px-4 py-3 font-medium {overdue ? 'text-red-600 dark:text-red-400' : 'text-[var(--fg)]'}">
                {e.return_date}
                {#if overdue}<span class="ml-1 text-[10px] font-bold">OVERDUE</span>{/if}
              </td>
              <td class="px-4 py-3 text-right">
                <button onclick={() => { returningId = e.id; returnDate = new Date().toISOString().slice(0,10); }}
                  class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-semibold
                         text-[var(--fg)] hover:bg-[var(--hover)] transition">
                  Record return
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>

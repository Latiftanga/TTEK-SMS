<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listPendingExeats, approveExeat, recordReturn, createExeat } from '$lib/api/housing';
  import { listStudents } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';

  interface Props { canManage: boolean; }
  const { canManage }: Props = $props();

  const qc = useQueryClient();

  const exeatsQ   = createQuery({ queryKey: ['exeats-pending'],   queryFn: listPendingExeats, staleTime: 60_000 });
  const studentsQ = createQuery({ queryKey: ['students-boarding'], queryFn: () => listStudents({ active_only: true }), staleTime: 5 * 60_000 });

  // ── Review / return ───────────────────────────────────────────────────────────
  const reviewMut = createMutation({
    mutationFn: ({ id, status }: { id: string; status: 'APPROVED' | 'REJECTED' }) => approveExeat(id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['exeats-pending'] }); toast.success('Exeat updated.'); },
    onError: () => toast.error('Could not update exeat.'),
  });

  const returnMut = createMutation({
    mutationFn: ({ id, date }: { id: string; date: string }) => recordReturn(id, date),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['exeats-pending'] }); toast.success('Return recorded.'); },
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

<div>
  <div class="mb-3 flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">
      Pending exeats
      {#if ($exeatsQ.data ?? []).length > 0}
        <span class="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700
                     dark:bg-amber-900/40 dark:text-amber-400">
          {($exeatsQ.data ?? []).length}
        </span>
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
  {:else if ($exeatsQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-8 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No pending exeats.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Student ID</th>
          <th class="hidden px-4 py-3 sm:table-cell">Destination</th>
          <th class="hidden px-4 py-3 sm:table-cell">Departs</th>
          <th class="hidden px-4 py-3 sm:table-cell">Returns</th>
          <th class="px-4 py-3">Actions</th>
        </tr></thead>
        <tbody>
          {#each $exeatsQ.data ?? [] as e (e.id)}
            <tr class="border-b border-[var(--border)] last:border-0">
              <td class="px-4 py-3 font-mono text-xs text-[var(--fg-muted)]">{e.student_id.slice(0,8)}…</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.destination}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.departure_date}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.return_date}</td>
              <td class="px-4 py-3">
                <div class="flex gap-2">
                  {#if e.status === 'PENDING'}
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
                  {:else if e.status === 'APPROVED'}
                    <button onclick={() => $returnMut.mutate({ id: e.id, date: new Date().toISOString().slice(0,10) })}
                      disabled={$returnMut.isPending}
                      class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-semibold
                             text-[var(--fg)] hover:bg-[var(--hover)] transition disabled:opacity-50">
                      Record return
                    </button>
                  {/if}
                </div>
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

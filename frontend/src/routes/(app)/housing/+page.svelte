<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { listHouses, createHouse, listPendingExeats, approveExeat, recordReturn, type House, type HouseGender } from '$lib/api/housing';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import PageHeader from '$lib/components/PageHeader.svelte';

  const qc = useQueryClient();
  const canManage = $derived($userRole === 'admin');

  const housesQ  = createQuery({ queryKey: ['houses'],         queryFn: listHouses,         staleTime: 2 * 60_000 });
  const exeatsQ  = createQuery({ queryKey: ['exeats-pending'], queryFn: listPendingExeats,  staleTime: 60_000 });

  // ── New house form ────────────────────────────────────────────────────────────
  let showForm = $state(false);
  let form = $state({ name: '', code: '', gender: 'MALE' as HouseGender, capacity: '', color: '' });
  let formErr = $state('');

  const createMut = createMutation({
    mutationFn: () => createHouse({
      name: form.name.trim(), code: form.code.trim().toUpperCase(),
      gender: form.gender,
      capacity: form.capacity ? parseInt(form.capacity) : undefined,
      color: form.color || undefined,
    }),
    onSuccess: (h: House) => {
      qc.invalidateQueries({ queryKey: ['houses'] });
      showForm = false;
      form = { name: '', code: '', gender: 'MALE', capacity: '', color: '' };
      goto(`/housing/${h.id}`);
    },
    onError: (e: unknown) => {
      formErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create house.';
    },
  });

  function handleCreate() {
    formErr = '';
    if (!form.name.trim()) { formErr = 'House name is required.'; return; }
    if (!form.code.trim()) { formErr = 'House code is required.'; return; }
    $createMut.mutate();
  }

  // ── Exeat actions ─────────────────────────────────────────────────────────────
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

  const GENDER_LABEL: Record<HouseGender, string> = { MALE: 'Boys', FEMALE: 'Girls', MIXED: 'Mixed' };
  const GENDER_COLOR: Record<HouseGender, string> = {
    MALE: 'bg-blue-50 text-blue-700 ring-blue-600/20 dark:bg-blue-950/40 dark:text-blue-400',
    FEMALE: 'bg-pink-50 text-pink-700 ring-pink-600/20 dark:bg-pink-950/40 dark:text-pink-400',
    MIXED: 'bg-purple-50 text-purple-700 ring-purple-600/20 dark:bg-purple-950/40 dark:text-purple-400',
  };
</script>

<svelte:head><title>Housing</title></svelte:head>

<PageHeader title="Housing" description="Boarding houses, room assignments, exeats, and night roll calls." />

<!-- Houses grid -->
<div class="mb-6">
  <div class="mb-3 flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">Houses</p>
    {#if canManage}
      <button onclick={() => { showForm = !showForm; formErr = ''; }}
        class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add house
      </button>
    {/if}
  </div>

  {#if showForm}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <p class="mb-3 text-sm font-semibold text-[var(--fg)]">New boarding house</p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div class="sm:col-span-2 lg:col-span-1">
          <label class="label">House name <span class="text-red-500">*</span></label>
          <input bind:value={form.name} placeholder="e.g. Nkrumah House" class="input" />
        </div>
        <div>
          <label class="label">Code <span class="text-red-500">*</span></label>
          <input bind:value={form.code} placeholder="e.g. NK" class="input" maxlength="20" />
        </div>
        <div>
          <label class="label">Gender</label>
          <select bind:value={form.gender} class="input">
            <option value="MALE">Boys</option>
            <option value="FEMALE">Girls</option>
            <option value="MIXED">Mixed</option>
          </select>
        </div>
        <div>
          <label class="label">Capacity</label>
          <input type="number" min="1" bind:value={form.capacity} placeholder="e.g. 120" class="input" />
        </div>
        <div>
          <label class="label">Colour (hex)</label>
          <input bind:value={form.color} placeholder="#3b82f6" class="input" maxlength="20" />
        </div>
      </div>
      {#if formErr}<p class="mt-2 text-xs text-red-500">{formErr}</p>{/if}
      <div class="mt-3 flex gap-2">
        <button onclick={handleCreate} disabled={$createMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$createMut.isPending ? 'Creating…' : 'Create house'}
        </button>
        <button onclick={() => { showForm = false; formErr = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if $housesQ.isPending}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each [1,2,3] as _}<div class="h-28 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}
    </div>
  {:else if ($housesQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No houses yet.{canManage ? ' Add one above.' : ''}</p>
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each $housesQ.data ?? [] as h (h.id)}
        <button onclick={() => goto(`/housing/${h.id}`)}
          class="group rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 text-left
                 transition hover:border-[var(--brand)]/40 hover:shadow-sm">
          <div class="mb-2 flex items-start justify-between">
            <div class="flex items-center gap-2">
              {#if h.color}
                <span class="h-3 w-3 shrink-0 rounded-full" style="background:{h.color}"></span>
              {/if}
              <p class="font-semibold text-[var(--fg)] group-hover:text-[var(--brand)] transition">{h.name}</p>
            </div>
            <span class="rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ring-inset {GENDER_COLOR[h.gender]}">
              {GENDER_LABEL[h.gender]}
            </span>
          </div>
          <div class="flex items-center gap-4 text-xs text-[var(--fg-muted)]">
            <span>{h.code}</span>
            {#if h.capacity}<span>Cap. {h.capacity}</span>{/if}
            <span>{h.rooms.length} room{h.rooms.length === 1 ? '' : 's'}</span>
            {#if !h.is_active}<span class="text-amber-500">Inactive</span>{/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

<!-- Pending exeats -->
<div>
  <p class="mb-3 text-sm font-semibold text-[var(--fg)]">
    Pending exeats
    {#if ($exeatsQ.data ?? []).length > 0}
      <span class="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700
                   dark:bg-amber-900/40 dark:text-amber-400">
        {($exeatsQ.data ?? []).length}
      </span>
    {/if}
  </p>

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
                      class="rounded-lg bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-700 transition hover:bg-green-100
                             dark:bg-green-950/40 dark:text-green-400 disabled:opacity-50">
                      Approve
                    </button>
                    <button onclick={() => $reviewMut.mutate({ id: e.id, status: 'REJECTED' })}
                      disabled={$reviewMut.isPending}
                      class="rounded-lg bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 transition hover:bg-red-100
                             dark:bg-red-950/40 dark:text-red-400 disabled:opacity-50">
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

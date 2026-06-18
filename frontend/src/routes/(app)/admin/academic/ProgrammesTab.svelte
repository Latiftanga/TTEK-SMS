<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listProgrammes, createProgramme, updateProgramme, type Programme } from '$lib/api/academic';
  import Pagination from '$lib/components/Pagination.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';

  const qc = useQueryClient();

  const programmesQuery = createQuery({ queryKey: ['programmes'], queryFn: listProgrammes, staleTime: 5 * 60_000 });

  // ── Filters ───────────────────────────────────────────────────────────────────
  let search       = $state('');
  let statusFilter = $state('active');
  let page         = $state(1);

  const all = $derived<Programme[]>($programmesQuery.data ?? []);

  const filtered = $derived(
    all.filter(p => {
      const q = search.trim().toLowerCase();
      if (q && !p.name.toLowerCase().includes(q) && !p.code.toLowerCase().includes(q)) return false;
      if (statusFilter === 'active'   && !p.is_active) return false;
      if (statusFilter === 'inactive' &&  p.is_active) return false;
      return true;
    }).sort((a, b) => a.name.localeCompare(b.name))
  );

  $effect(() => { search; statusFilter; page = 1; });

  const PAGE  = 20;
  const paged = $derived(filtered.slice((page - 1) * PAGE, page * PAGE));

  // ── Create form ───────────────────────────────────────────────────────────────
  let showForm  = $state(false);
  let form      = $state({ code: '', name: '' });
  let formError = $state('');

  const createMut = createMutation({
    mutationFn: createProgramme,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['programmes'] }); showForm = false; form = { code: '', name: '' }; formError = ''; },
    onError: (e: unknown) => { formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create programme.'; },
  });

  // ── Inline edit ───────────────────────────────────────────────────────────────
  let editingId = $state<string | null>(null);
  let editForm  = $state({ code: '', name: '' });
  let editError = $state('');

  const updateMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { code?: string; name?: string; is_active?: boolean } }) => updateProgramme(id, req),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['programmes'] }); editingId = null; editError = ''; },
    onError: (e: unknown) => { editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update.'; },
  });

  function startEdit(p: Programme) { editingId = p.id; editForm = { code: p.code, name: p.name }; editError = ''; }

  function submitCreate() {
    formError = '';
    if (!form.code.trim() || !form.name.trim()) { formError = 'Code and name are required.'; return; }
    $createMut.mutate({ code: form.code.trim().toUpperCase(), name: form.name.trim() });
  }

  function submitEdit() {
    editError = '';
    if (!editForm.code.trim() || !editForm.name.trim()) { editError = 'Code and name are required.'; return; }
    $updateMut.mutate({ id: editingId!, req: { code: editForm.code, name: editForm.name } });
  }

  const PILL = (active: boolean) => `rounded-md px-3 py-1 text-xs font-medium transition ${active ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}`;
</script>

<div class="space-y-4">
  <!-- Toolbar -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
        <input bind:value={search} type="search" placeholder="Search programmes…"
          class="h-9 w-48 rounded-xl border border-[var(--border)] bg-[var(--card)] pl-9 pr-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 sm:w-60" />
      </div>
      <div class="flex rounded-lg border border-[var(--border)] bg-[var(--bg)] p-0.5">
        {#each [['all','All'],['active','Active'],['inactive','Inactive']] as [v, l]}
          <button onclick={() => { statusFilter = v; page = 1; }} class={PILL(statusFilter === v)}>{l}</button>
        {/each}
      </div>
    </div>
    <button onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90" style="background-color: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
      Add programme
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Programme</h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code</label>
          <input bind:value={form.code} placeholder="e.g. SCI" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
          <input bind:value={form.name} placeholder="e.g. General Science" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={submitCreate} disabled={$createMut.isPending} class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">{$createMut.isPending ? 'Creating…' : 'Create programme'}</button>
        <button onclick={() => { showForm = false; formError = ''; }} class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">Cancel</button>
      </div>
    </div>
  {/if}

  {#if $programmesQuery.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="skeleton h-12"></div>{/each}</div>
  {:else if all.length === 0}
    <EmptyState
      iconPath="M4.26 10.147a60.438 60.438 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.636 50.636 0 00-2.658-.813A59.906 59.906 0 0112 3.493a59.903 59.903 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"
      title="No programmes yet."
      description="Add your first SHS programme to enable programme-based classes."
    />
  {:else if filtered.length === 0}
    <EmptyState
      iconPath="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
      title="No programmes match these filters."
      action={() => { search = ''; statusFilter = 'all'; }}
      actionLabel="Clear filters"
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Code</th>
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Name</th>
            <th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Status</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each paged as prog (prog.id)}
            {#if editingId === prog.id}
              <tr class="bg-[var(--bg)]">
                <td class="px-3 py-2"><input bind:value={editForm.code} class="w-20 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 font-mono text-xs uppercase text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" /></td>
                <td class="px-3 py-2">
                  <input bind:value={editForm.name} class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                  {#if editError}<p class="mt-1 text-[11px] text-red-500">{editError}</p>{/if}
                </td>
                <td class="hidden px-4 py-2 sm:table-cell"></td>
                <td class="px-3 py-2 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button onclick={submitEdit} disabled={$updateMut.isPending} class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">{$updateMut.isPending ? '…' : 'Save'}</button>
                    <button onclick={() => { editingId = null; editError = ''; }} class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--card)]">Cancel</button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr class="group transition hover:bg-[var(--bg)]">
                <td class="px-4 py-2.5 font-mono text-xs text-[var(--fg-muted)]">{prog.code}</td>
                <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{prog.name}</td>
                <td class="hidden px-4 py-2.5 sm:table-cell"><span class="badge {prog.is_active ? 'badge-success' : 'badge-neutral'}">{prog.is_active ? 'Active' : 'Inactive'}</span></td>
                <td class="px-4 py-2.5 text-right">
                  <div class="flex items-center justify-end gap-1 opacity-0 transition group-hover:opacity-100">
                    <button onclick={() => startEdit(prog)} class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                      Edit
                    </button>
                    <button onclick={() => $updateMut.mutate({ id: prog.id, req: { is_active: !prog.is_active } })} disabled={$updateMut.isPending}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium disabled:opacity-40 {prog.is_active ? 'text-red-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30' : 'text-green-500 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-950/30'}">
                      {#if prog.is_active}
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
    <Pagination total={filtered.length} pageSize={PAGE} {page} label="programmes" onPageChange={(p) => page = p} />
  {/if}
</div>

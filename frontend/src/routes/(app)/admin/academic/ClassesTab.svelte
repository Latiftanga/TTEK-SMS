<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listClasses, listProgrammes, updateClass, type SchoolClass, type Programme } from '$lib/api/academic';
  import ClassCreateForm from './ClassCreateForm.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';

  const { schoolType } = $props<{ schoolType: string }>();
  const qc = useQueryClient();

  const classesQuery = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 2 * 60_000 });
  const programmesQuery = createQuery({ queryKey: ['programmes'], queryFn: listProgrammes, enabled: schoolType === 'SHS', staleTime: 5 * 60_000 });

  // ── Filters ──────────────────────────────────────────────────────────────────
  let search          = $state('');
  let statusFilter    = $state('all');
  let filterYear      = $state('');
  let filterProgramme = $state('');  // SHS
  let filterLevel     = $state('');  // Basic

  const all = $derived<SchoolClass[]>($classesQuery.data ?? []);
  const availableLevels = $derived([...new Set(all.map(c => c.level))].sort());
  const availableYears  = $derived([...new Set(all.filter(c => !filterLevel || c.level === filterLevel).map(c => c.year_group))].sort((a, b) => a - b));
  const availableProgs  = $derived([...new Map(all.filter(c => c.programme_id).map(c => [c.programme_id, { id: c.programme_id!, name: c.programme_name ?? '' }])).values()]);

  const filtered = $derived(
    all.filter(c => {
      const q = search.trim().toLowerCase();
      if (q && !c.display_name.toLowerCase().includes(q) && !(c.programme_name ?? '').toLowerCase().includes(q)) return false;
      if (statusFilter === 'active'   &&  !c.is_active) return false;
      if (statusFilter === 'inactive' &&   c.is_active) return false;
      if (schoolType === 'SHS') {
        if (filterYear      && c.year_group !== Number(filterYear)) return false;
        if (filterProgramme && c.programme_id !== filterProgramme)  return false;
      } else {
        if (filterLevel && c.level      !== filterLevel)         return false;
        if (filterYear  && c.year_group !== Number(filterYear)) return false;
      }
      return true;
    }).sort((a, b) => a.display_name.localeCompare(b.display_name))
  );

  $effect(() => { if (filterLevel) filterYear = ''; });

  // ── Pagination ────────────────────────────────────────────────────────────────
  const PAGE = 20;
  let page = $state(1);
  $effect(() => { search; statusFilter; filterYear; filterProgramme; filterLevel; page = 1; });
  const paged = $derived(filtered.slice((page - 1) * PAGE, page * PAGE));

  // ── Inline edit ───────────────────────────────────────────────────────────────
  let editingId = $state<string | null>(null);
  let editForm  = $state({ stream: '', capacity: '', programme_id: '' });
  let editError = $state('');

  const updateMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { stream?: string | null; capacity?: number | null; is_active?: boolean; programme_id?: string } }) => updateClass(id, req),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['classes'] }); editingId = null; editError = ''; },
    onError: (e: unknown) => { editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update class.'; },
  });

  function startEdit(cls: SchoolClass) {
    editingId = cls.id;
    editForm = { stream: cls.stream ?? '', capacity: cls.capacity?.toString() ?? '', programme_id: cls.programme_id ?? '' };
    editError = '';
  }

  function saveEdit() {
    editError = '';
    $updateMut.mutate({ id: editingId!, req: { stream: editForm.stream.trim() || null, capacity: editForm.capacity ? Number(editForm.capacity) : null, ...(schoolType === 'SHS' && editForm.programme_id ? { programme_id: editForm.programme_id } : {}) } });
  }


  const PILL = (active: boolean) => `rounded-md px-3 py-1 text-xs font-medium transition ${active ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}`;
  const SEL  = "rounded-lg border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none";
</script>

<div class="space-y-4">
  <!-- Toolbar -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <!-- Search -->
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
        <input bind:value={search} type="search" placeholder="Search classes…"
          class="h-9 w-48 rounded-xl border border-[var(--border)] bg-[var(--card)] pl-9 pr-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 sm:w-56" />
      </div>
      <!-- Status -->
      <div class="flex rounded-lg border border-[var(--border)] bg-[var(--bg)] p-0.5">
        {#each [['all','All'],['active','Active'],['inactive','Inactive']] as [v, l]}
          <button onclick={() => { statusFilter = v; page = 1; }} class={PILL(statusFilter === v)}>{l}</button>
        {/each}
      </div>
      <!-- Dimension filters -->
      {#if !$classesQuery.isPending && all.length > 0}
        {#if schoolType === 'SHS'}
          <select bind:value={filterYear} class={SEL}>
            <option value="">All years</option>
            {#each availableYears as yr}<option value={String(yr)}>Year {yr}</option>{/each}
          </select>
          <select bind:value={filterProgramme} class={SEL}>
            <option value="">All programmes</option>
            {#each availableProgs as p}<option value={p.id}>{p.name}</option>{/each}
          </select>
        {:else}
          <select bind:value={filterLevel} class={SEL}>
            <option value="">All levels</option>
            {#each availableLevels as lvl}<option value={lvl}>{lvl}</option>{/each}
          </select>
          <select bind:value={filterYear} class={SEL}>
            <option value="">All years</option>
            {#each availableYears as yr}<option value={String(yr)}>{filterLevel ? `${filterLevel} ${yr}` : `Year ${yr}`}</option>{/each}
          </select>
        {/if}
      {/if}
    </div>
    <ClassCreateForm {schoolType} programmes={$programmesQuery.data ?? []} />
  </div>

  {#if $classesQuery.isPending}
    <div class="space-y-2">{#each [1,2,3,4] as _}<div class="skeleton h-14"></div>{/each}</div>
  {:else if all.length === 0}
    <EmptyState
      iconPath="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
      title="No classes yet."
      description="Add your first class using the button above."
    />
  {:else if filtered.length === 0}
    <EmptyState
      iconPath="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"
      title="No classes match these filters."
      description="Try adjusting or clearing your search and filters."
      action={() => { search = ''; statusFilter = 'all'; filterYear = ''; filterProgramme = ''; filterLevel = ''; }}
      actionLabel="Clear filters"
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Class</th>
            {#if schoolType === 'SHS'}<th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Programme</th>{/if}
            <th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Capacity</th>
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each paged as cls (cls.id)}
            {#if editingId === cls.id}
              <tr class="bg-[var(--bg)]">
                <td class="px-4 py-2 font-medium text-[var(--fg)]">{cls.display_name}</td>
                {#if schoolType === 'SHS'}
                  <td class="hidden px-4 py-2 sm:table-cell">
                    <select bind:value={editForm.programme_id} class="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
                      <option value="">No programme</option>
                      {#each ($programmesQuery.data ?? []).filter((p: Programme) => p.is_active) as prog (prog.id)}<option value={prog.id}>{prog.name}</option>{/each}
                    </select>
                  </td>
                {/if}
                <td class="hidden px-3 py-2 sm:table-cell">
                  <input type="number" bind:value={editForm.capacity} placeholder="—" class="w-20 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                </td>
                <td class="px-3 py-2">
                  <input bind:value={editForm.stream} placeholder="Stream" class="w-24 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                  {#if editError}<p class="mt-1 text-[11px] text-red-500">{editError}</p>{/if}
                </td>
                <td class="px-3 py-2 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button onclick={saveEdit} disabled={$updateMut.isPending} class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">{$updateMut.isPending ? '…' : 'Save'}</button>
                    <button onclick={() => { editingId = null; editError = ''; }} class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--card)]">Cancel</button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr class="group transition hover:bg-[var(--bg)]">
                <td class="px-4 py-2.5 font-medium">
                  <a href="/admin/academic/classes/{cls.id}" class="text-[var(--fg)] hover:text-[var(--brand)] hover:underline underline-offset-2">{cls.display_name}</a>
                </td>
                {#if schoolType === 'SHS'}<td class="hidden px-4 py-2.5 text-[var(--fg-muted)] sm:table-cell">{cls.programme_name ?? '—'}</td>{/if}
                <td class="hidden px-4 py-2.5 text-[var(--fg-muted)] sm:table-cell">{cls.capacity ?? '—'}</td>
                <td class="px-4 py-2.5"><span class="badge {cls.is_active ? 'badge-success' : 'badge-neutral'}">{cls.is_active ? 'Active' : 'Inactive'}</span></td>
                <td class="px-4 py-2.5 text-right">
                  <div class="flex items-center justify-end gap-1 opacity-0 transition group-hover:opacity-100">
                    <a href="/admin/academic/classes/{cls.id}" class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--brand)] hover:bg-[var(--bg)]">
                      Manage →
                    </a>
                    <button onclick={() => startEdit(cls)} class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                      Edit
                    </button>
                    <button onclick={() => $updateMut.mutate({ id: cls.id, req: { is_active: !cls.is_active } })}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium {cls.is_active ? 'text-red-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30' : 'text-green-500 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-950/30'}">
                      {#if cls.is_active}
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
    <Pagination total={filtered.length} pageSize={PAGE} {page} label="classes" onPageChange={(p) => page = p} />
  {/if}
</div>

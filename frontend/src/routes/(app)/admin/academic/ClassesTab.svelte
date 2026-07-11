<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listClasses, listProgrammes, updateClass, type SchoolClass } from '$lib/api/academic';
  import ClassCreateForm from './ClassCreateForm.svelte';
  import ClassEditModal from './ClassEditModal.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  const { schoolType }: { schoolType: string } = $props();
  const qc = useQueryClient();

  let showAddForm       = $state(false);
  let editModal         = $state<SchoolClass | null>(null);
  let confirmDeactivate = $state<SchoolClass | null>(null);

  const classesQuery    = createQuery({ queryKey: ['classes'],    queryFn: listClasses,    staleTime: 2 * 60_000 });
  const programmesQuery = createQuery({ queryKey: ['programmes'], queryFn: listProgrammes, enabled: schoolType === 'SHS', staleTime: 5 * 60_000 });

  // ── Filters from URL ──────────────────────────────────────────────────────────
  const search          = $derived($page.url.searchParams.get('q')      ?? '');
  const statusFilter    = $derived($page.url.searchParams.get('status') ?? 'all');
  const filterYear      = $derived($page.url.searchParams.get('year')   ?? '');
  const filterProgramme = $derived($page.url.searchParams.get('prog')   ?? '');
  const filterLevel     = $derived($page.url.searchParams.get('level')  ?? '');
  const currentPage     = $derived(Number($page.url.searchParams.get('p') ?? '1'));

  function setParam(key: string, value: string, extra: Record<string, string> | undefined = undefined) {
    const url = new URL($page.url);
    if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
    if (extra) { for (const [k, v] of Object.entries(extra)) { if (v) url.searchParams.set(k, v); else url.searchParams.delete(k); } }
    url.searchParams.delete('p');
    goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
  }
  function setPage(p: number) {
    const url = new URL($page.url);
    if (p > 1) url.searchParams.set('p', String(p)); else url.searchParams.delete('p');
    goto(url.toString(), { replaceState: true, keepFocus: true, noScroll: true });
  }
  function clearFilters() { goto($page.url.pathname, { replaceState: true, noScroll: true }); }

  // ── Derived data ──────────────────────────────────────────────────────────────
  const all = $derived<SchoolClass[]>($classesQuery.data ?? []);
  const availableLevels = $derived([...new Set(all.map(c => c.level))].sort());
  const availableYears  = $derived([...new Set(all.filter(c => !filterLevel || c.level === filterLevel).map(c => c.year_group))].sort((a, b) => a - b));
  const availableProgs  = $derived([...new Map(all.filter(c => c.programme_id).map(c => [c.programme_id, { id: c.programme_id!, name: c.programme_name ?? '' }])).values()]);

  const filtered = $derived(
    all.filter(c => {
      const q = search.trim().toLowerCase();
      if (q && !c.display_name.toLowerCase().includes(q) && !(c.programme_name ?? '').toLowerCase().includes(q)) return false;
      if (statusFilter === 'active'   && !c.is_active) return false;
      if (statusFilter === 'inactive' &&  c.is_active) return false;
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

  const PAGE  = 20;
  const paged = $derived(filtered.slice((currentPage - 1) * PAGE, currentPage * PAGE));
  const hasFilters = $derived(!!(search || (statusFilter !== 'all') || filterYear || filterProgramme || filterLevel));
  const activeCount = $derived(all.filter(c => c.is_active).length);

  const toggleMut = createMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => updateClass(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['classes'] }),
  });

  // Level colours for avatars
  const LEVEL_COLOR: Record<string, string> = {
    SHS: '#7c3aed', JHS: '#2563eb', PRIMARY: '#0d9488',
    KINDERGARTEN: '#d97706', NURSERY: '#f59e0b',
  };
  function levelBg(level: string) { return LEVEL_COLOR[level] ?? '#6366f1'; }

  const PILL = (active: boolean) => `rounded-md px-3 py-1 text-xs font-medium transition ${active ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}`;
  const SEL  = "rounded-lg border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none";
</script>

<div class="space-y-4">
  <!-- Toolbar -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
        <input value={search} oninput={(e) => setParam('q', (e.target as HTMLInputElement).value)} type="search" placeholder="Search classes…"
          class="h-9 w-48 rounded-xl border border-[var(--border)] bg-[var(--card)] pl-9 pr-3 text-sm placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none sm:w-56" />
      </div>
      <div class="flex rounded-lg border border-[var(--border)] bg-[var(--bg)] p-0.5">
        {#each [['all','All'],['active','Active'],['inactive','Inactive']] as [v, l]}
          <button onclick={() => setParam('status', v)} class={PILL(statusFilter === v)}>{l}</button>
        {/each}
      </div>
      {#if !$classesQuery.isPending && all.length > 0}
        {#if schoolType === 'SHS'}
          <select value={filterYear} onchange={(e) => setParam('year', (e.target as HTMLSelectElement).value)} class={SEL}>
            <option value="">All years</option>
            {#each availableYears as yr}<option value={String(yr)}>Year {yr}</option>{/each}
          </select>
          <select value={filterProgramme} onchange={(e) => setParam('prog', (e.target as HTMLSelectElement).value)} class={SEL}>
            <option value="">All programmes</option>
            {#each availableProgs as p}<option value={p.id}>{p.name}</option>{/each}
          </select>
        {:else}
          <select value={filterLevel} onchange={(e) => setParam('level', (e.target as HTMLSelectElement).value, { year: '' })} class={SEL}>
            <option value="">All levels</option>
            {#each availableLevels as lvl}<option value={lvl}>{lvl}</option>{/each}
          </select>
          <select value={filterYear} onchange={(e) => setParam('year', (e.target as HTMLSelectElement).value)} class={SEL}>
            <option value="">All years</option>
            {#each availableYears as yr}<option value={String(yr)}>{filterLevel ? `${filterLevel} ${yr}` : `Year ${yr}`}</option>{/each}
          </select>
        {/if}
      {/if}
      {#if hasFilters}
        <button onclick={clearFilters} class="text-xs text-[var(--fg-muted)] underline transition hover:text-[var(--fg)]">Clear</button>
      {/if}
    </div>
    <button onclick={() => showAddForm = !showAddForm} class="btn-primary">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
      Add class
    </button>
  </div>

  {#if showAddForm}
    <ClassCreateForm {schoolType} programmes={$programmesQuery.data ?? []} onClose={() => showAddForm = false} />
  {/if}

  {#if $classesQuery.isPending}
    <div class="space-y-2">{#each [1,2,3,4] as _}<div class="skeleton h-16"></div>{/each}</div>
  {:else if all.length === 0}
    <EmptyState
      iconPath="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
      title="No classes yet."
      description="Add your first class using the button above."
    />
  {:else}
    <!-- Summary strip -->
    {#if !hasFilters}
      <div class="flex gap-4 text-xs text-[var(--fg-muted)]">
        <span><strong class="text-[var(--fg)]">{all.length}</strong> classes total</span>
        <span><strong class="text-green-600 dark:text-green-400">{activeCount}</strong> active</span>
        {#if all.length - activeCount > 0}
          <span><strong class="text-[var(--fg-subtle)]">{all.length - activeCount}</strong> inactive</span>
        {/if}
      </div>
    {/if}

    {#if filtered.length === 0}
      <EmptyState
        iconPath="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"
        title="No classes match these filters."
        description="Try adjusting or clearing your search and filters."
        action={clearFilters}
        actionLabel="Clear filters"
      />
    {:else}
      <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[var(--border)] bg-[var(--hover)]/40 text-left">
              <th class="px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Class</th>
              <th class="hidden px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)] sm:table-cell">Capacity</th>
              <th class="px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Status</th>
              <th class="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)]">
            {#each paged as cls (cls.id)}
              <tr class="transition hover:bg-[var(--hover)]/60">
                <!-- Class name + level avatar -->
                <td class="px-4 py-3">
                  <div class="flex items-center gap-3">
                    <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[11px] font-bold text-white"
                         style="background: {levelBg(cls.level)}">
                      {cls.level.slice(0, 3)}
                    </div>
                    <div class="min-w-0">
                      <p class="font-semibold text-[var(--fg)] leading-snug">{cls.display_name}</p>
                      {#if cls.programme_name}
                        <p class="text-[11px] text-[var(--fg-muted)]">{cls.programme_name}</p>
                      {:else}
                        <p class="text-[11px] text-[var(--fg-subtle)]">{cls.level} · Year {cls.year_group}</p>
                      {/if}
                    </div>
                  </div>
                </td>
                <!-- Capacity -->
                <td class="hidden px-4 py-3 text-sm text-[var(--fg-muted)] sm:table-cell">
                  {cls.capacity ?? '—'}
                </td>
                <!-- Status -->
                <td class="px-4 py-3">
                  <span class="badge {cls.is_active ? 'badge-success' : 'badge-neutral'}">
                    {cls.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <!-- Actions -->
                <td class="px-4 py-3">
                  <div class="flex items-center justify-end gap-1.5">
                    <a href="/admin/academic/classes/{cls.id}"
                      class="inline-flex items-center gap-1 rounded-lg border border-[var(--brand)]/30 bg-[var(--brand)]/8 px-3 py-1.5 text-xs font-semibold transition hover:bg-[var(--brand)]/15"
                      style="color: var(--brand)">
                      Manage
                      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/>
                      </svg>
                    </a>
                    <button onclick={() => editModal = cls} title="Edit"
                      class="rounded-lg p-1.5 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"/></svg>
                    </button>
                    <button onclick={() => cls.is_active ? (confirmDeactivate = cls) : $toggleMut.mutate({ id: cls.id, is_active: true })} title={cls.is_active ? 'Deactivate' : 'Activate'}
                      class="rounded-lg p-1.5 transition hover:bg-[var(--hover)] {cls.is_active ? 'text-[var(--fg-subtle)] hover:text-red-500' : 'text-[var(--fg-subtle)] hover:text-green-500'}">
                      {#if cls.is_active}
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                      {:else}
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                      {/if}
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <Pagination total={filtered.length} pageSize={PAGE} page={currentPage} label="classes" onPageChange={setPage} />
    {/if}
  {/if}
</div>

<ConfirmModal
  open={!!confirmDeactivate}
  title="Deactivate {confirmDeactivate?.display_name ?? 'class'}?"
  message="Students will no longer be enrollable in this class. You can reactivate it at any time."
  confirmLabel="Deactivate"
  isPending={$toggleMut.isPending}
  onConfirm={() => { $toggleMut.mutate({ id: confirmDeactivate!.id, is_active: false }); confirmDeactivate = null; }}
  onCancel={() => confirmDeactivate = null}
/>

{#if editModal}
  <ClassEditModal cls={editModal} onClose={() => editModal = null} />
{/if}

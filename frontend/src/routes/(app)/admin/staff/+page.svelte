<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { listStaff, type StaffSummary } from '$lib/api/staff';
  import StaffForm        from './StaffForm.svelte';
  import StaffImportModal from './StaffImportModal.svelte';
  import Badge            from '$lib/components/Badge.svelte';
  import EmptyState       from '$lib/components/EmptyState.svelte';

  let drawerOpen   = $state(false);
  let importOpen   = $state(false);
  let search       = $state('');
  let activeOnly   = $state(true);
  let genderFilter = $state('');
  let jobFilter    = $state('');

  const query = createQuery({
    queryKey: ['staff', activeOnly],
    queryFn:  () => listStaff({ active_only: activeOnly }),
    staleTime: 2 * 60_000,
  });

  const stats = $derived.by(() => {
    const all: StaffSummary[] = $query.data ?? [];
    return { total: all.length, active: all.filter(s => s.is_active).length };
  });

  const categoryOptions = $derived.by(() => {
    const names = new Set(($query.data ?? []).map(s => s.category_name).filter(Boolean));
    return [...names].sort() as string[];
  });

  const filtered = $derived.by(() => {
    let list: StaffSummary[] = $query.data ?? [];
    const q = search.trim().toLowerCase();
    if (q)           list = list.filter(s =>
      s.display_name.toLowerCase().includes(q) ||
      s.staff_number.toLowerCase().includes(q) ||
      s.position_names.some(n => n.toLowerCase().includes(q)) ||
      (s.category_name ?? '').toLowerCase().includes(q)
    );
    if (genderFilter) list = list.filter(s => s.gender === genderFilter);
    if (jobFilter)    list = list.filter(s => s.category_name === jobFilter);
    return list;
  });

  let exportMenuOpen = $state(false);

  async function doExport(type: 'excel' | 'pdf') {
    exportMenuOpen = false;
    const { exportStaffExcel, exportStaffPdf } = await import('$lib/api/staff');
    if (type === 'excel') await exportStaffExcel();
    else await exportStaffPdf();
  }

  function initials(s: StaffSummary) { return (s.first_name[0] + s.last_name[0]).toUpperCase(); }

  const GENDER_BG: Record<string, string> = { MALE: '#3B82F6', FEMALE: '#EC4899' };
</script>

<StaffForm
  open={drawerOpen}
  onSuccess={(staff) => { drawerOpen = false; goto(`/admin/staff/${staff.id}`); }}
  onCancel={() => drawerOpen = false}
/>
<StaffImportModal open={importOpen} onClose={() => importOpen = false} />

<div class="space-y-5">

  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold text-[var(--fg)]">Staff</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
        {#if filtered.length !== stats.total}
          Showing {filtered.length} of {stats.total} member{stats.total !== 1 ? 's' : ''}
        {:else}
          {stats.total} member{stats.total !== 1 ? 's' : ''} on record
        {/if}
      </p>
    </div>
    <div class="flex gap-2">
      <div class="relative">
        <button onclick={() => exportMenuOpen = !exportMenuOpen}
          class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)]
                 px-3 py-2 text-sm font-medium text-[var(--fg-muted)] transition
                 hover:bg-[var(--hover)] hover:text-[var(--fg)]">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/>
          </svg>
          Export
          <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
          </svg>
        </button>
        {#if exportMenuOpen}
          <div class="absolute right-0 top-full z-10 mt-1 min-w-36 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-lg">
            <button onclick={() => doExport('excel')}
              class="w-full px-4 py-2.5 text-left text-sm text-[var(--fg)] transition hover:bg-[var(--hover)]">
              Excel (.xlsx)
            </button>
            <button onclick={() => doExport('pdf')}
              class="w-full px-4 py-2.5 text-left text-sm text-[var(--fg)] transition hover:bg-[var(--hover)]">
              PDF
            </button>
          </div>
        {/if}
      </div>
      <button onclick={() => importOpen = true}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)]
               px-3 py-2 text-sm font-medium text-[var(--fg-muted)] transition
               hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
        </svg>
        Import
      </button>
      <button onclick={() => drawerOpen = true}
        class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white
               shadow-sm transition hover:opacity-90"
        style="background-color: var(--brand)">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add staff
      </button>
    </div>
  </div>

  <!-- Stats strip -->
  {#if $query.isSuccess && stats.total > 0}
    <div class="flex flex-wrap gap-2">
      {#each [
        { label: 'Total',  value: stats.total,  cls: 'text-[var(--fg)]' },
        { label: 'Active', value: stats.active, cls: 'text-green-600 dark:text-green-400' },
      ] as chip}
        <div class="flex items-baseline gap-1.5 rounded-xl border border-[var(--border)]
                    bg-[var(--card)] px-3.5 py-2">
          <span class="text-base font-bold {chip.cls}">{chip.value}</span>
          <span class="text-xs text-[var(--fg-muted)]">{chip.label}</span>
        </div>
      {/each}
      <label class="flex cursor-pointer items-baseline gap-1.5 rounded-xl border border-[var(--border)]
                    bg-[var(--card)] px-3.5 py-2 transition hover:bg-[var(--hover)]">
        <input type="checkbox" bind:checked={activeOnly} class="accent-[var(--brand)] mr-0.5 h-3 w-3" />
        <span class="text-xs text-[var(--fg-muted)]">Active only</span>
      </label>
    </div>
  {/if}

  <!-- Search + filters -->
  <div class="flex flex-wrap gap-2">
    <div class="relative min-w-48 flex-1">
      <svg class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
           fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" d="m21 21-4.35-4.35"/>
      </svg>
      <input bind:value={search} placeholder="Search name, ID, category, position…"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2.5 pl-9 pr-4
               text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
               focus:border-[var(--brand)] focus:outline-none" />
    </div>
    <select bind:value={genderFilter}
      class="h-10 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 text-sm
             text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
      <option value="">All genders</option>
      <option value="MALE">Male</option>
      <option value="FEMALE">Female</option>
    </select>
    {#if categoryOptions.length > 0}
      <select bind:value={jobFilter}
        class="h-10 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 text-sm
               text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
        <option value="">All categories</option>
        {#each (categoryOptions) as name}
          <option value={name}>{name}</option>
        {/each}
      </select>
    {/if}
  </div>

  <!-- Table -->
  {#if $query.isPending}
    <div class="space-y-2">
      {#each [1,2,3,4,5] as _}
        <div class="skeleton h-16"></div>
      {/each}
    </div>
  {:else if $query.isError}
    <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40
                p-4 text-sm text-red-600 dark:text-red-400">
      Could not load staff list.
      <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
    </div>
  {:else if filtered.length === 0}
    <EmptyState
      iconPath="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
      title={search || genderFilter || jobFilter ? 'No staff match your filters.' : 'No staff on record yet.'}
      description={search || genderFilter || jobFilter
        ? 'Try adjusting or clearing your search and filters.'
        : 'Add your first staff member to get started.'}
      action={search || genderFilter || jobFilter
        ? () => { search = ''; genderFilter = ''; jobFilter = ''; }
        : () => { drawerOpen = true; }}
      actionLabel={search || genderFilter || jobFilter ? 'Clear filters' : 'Add first staff member'}
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Staff</th>
            <th class="hidden px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] md:table-cell">Position</th>
            <th class="hidden px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] lg:table-cell">Contact</th>
            <th class="px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each filtered as s (s.id)}
            <tr onclick={() => goto(`/admin/staff/${s.id}`)}
                class="group cursor-pointer transition hover:bg-[var(--hover)]">
              <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl
                              text-xs font-bold text-white"
                       style="background-color: {GENDER_BG[s.gender ?? ''] ?? 'var(--brand)'}">
                    {initials(s)}
                  </div>
                  <div class="min-w-0">
                    <p class="font-semibold text-[var(--fg)]">{s.display_name}</p>
                    <div class="mt-0.5 flex items-center gap-2 flex-wrap">
                      <span class="text-xs text-[var(--fg-muted)]">{s.staff_number}</span>
                      {#if s.category_name}
                        <span class="text-xs text-[var(--fg-muted)]">· {s.category_name}</span>
                      {/if}
                    </div>
                  </div>
                </div>
              </td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">
                {s.position_names.join(', ') || '—'}
              </td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] lg:table-cell">
                {s.phone ?? s.email ?? '—'}
              </td>
              <td class="px-4 py-3">
                <Badge
                  label={s.is_active ? 'Active' : 'Inactive'}
                  color={s.is_active ? 'green' : 'gray'}
                  variant="dot"
                />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

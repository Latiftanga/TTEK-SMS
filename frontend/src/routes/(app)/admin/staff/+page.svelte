<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { listStaff, type StaffSummary } from '$lib/api/staff';
  import StaffForm from './StaffForm.svelte';

  let drawerOpen    = $state(false);
  let search        = $state('');
  let activeOnly    = $state(true);
  let genderFilter  = $state('');
  let categoryFilter = $state('');

  const query = createQuery({
    queryKey: ['staff', activeOnly],
    queryFn:  () => listStaff({ active_only: activeOnly }),
    staleTime: 2 * 60_000,
  });

  const stats = $derived(() => {
    const all: StaffSummary[] = $query.data ?? [];
    return {
      total:      all.length,
      teaching:   all.filter(s => s.staff_category === 'TEACHING').length,
      nonTeaching:all.filter(s => s.staff_category === 'NON_TEACHING').length,
      active:     all.filter(s => s.is_active).length,
    };
  });

  const filtered = $derived(() => {
    let list: StaffSummary[] = $query.data ?? [];
    const q = search.trim().toLowerCase();
    if (q)              list = list.filter(s =>
      s.display_name.toLowerCase().includes(q) ||
      s.staff_number.toLowerCase().includes(q) ||
      s.position_names.some(n => n.toLowerCase().includes(q))
    );
    if (genderFilter)   list = list.filter(s => s.gender === genderFilter);
    if (categoryFilter) list = list.filter(s => s.staff_category === categoryFilter);
    return list;
  });

  function exportCSV() {
    const rows = filtered();
    if (!rows.length) return;
    const esc = (v: string | null | undefined) => `"${(v ?? '').replace(/"/g, '""')}"`;
    const lines = [
      ['Name','Staff No.','Category','Position','Gender','Phone','Email','Joined','Status'].join(','),
      ...rows.map(s => [
        esc(s.display_name), esc(s.staff_number),
        s.staff_category ?? '', esc(s.position_names.join('; ')),
        s.gender ?? '', s.phone ?? '', s.email ?? '',
        s.joined_date ?? '', s.is_active ? 'Active' : 'Inactive',
      ].join(',')),
    ];
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' }));
    const a = Object.assign(document.createElement('a'), {
      href: url, download: `staff-${new Date().toISOString().slice(0, 10)}.csv`,
    });
    a.click();
    URL.revokeObjectURL(url);
  }

  function initials(s: StaffSummary) { return (s.first_name[0] + s.last_name[0]).toUpperCase(); }

  const GENDER_BG: Record<string, string> = { MALE: '#3B82F6', FEMALE: '#EC4899' };
  const CAT_STYLE: Record<string, string> = {
    TEACHING:     'bg-teal-50 dark:bg-teal-950/40 text-teal-700 dark:text-teal-400',
    NON_TEACHING: 'bg-violet-50 dark:bg-violet-950/40 text-violet-600 dark:text-violet-400',
  };
  const CAT_LABEL: Record<string, string> = { TEACHING: 'Teaching', NON_TEACHING: 'Non-Teaching' };
</script>

<StaffForm
  open={drawerOpen}
  onSuccess={(staff) => { drawerOpen = false; goto(`/admin/staff/${staff.id}`); }}
  onCancel={() => drawerOpen = false}
/>

<div class="space-y-5">

  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold text-[var(--fg)]">Staff</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
        {#if filtered().length !== stats().total}
          Showing {filtered().length} of {stats().total} member{stats().total !== 1 ? 's' : ''}
        {:else}
          {stats().total} member{stats().total !== 1 ? 's' : ''} on record
        {/if}
      </p>
    </div>
    <div class="flex gap-2">
      <button onclick={exportCSV} disabled={!filtered().length}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)]
               px-3 py-2 text-sm font-medium text-[var(--fg-muted)] transition
               hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:opacity-40">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/>
        </svg>
        Export
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
  {#if $query.isSuccess && stats().total > 0}
    <div class="flex flex-wrap gap-2">
      {#each [
        { label: 'Total',        value: stats().total,       active: !categoryFilter,              cls: 'text-[var(--fg)]' },
        { label: 'Teaching',     value: stats().teaching,    active: categoryFilter === 'TEACHING',    cls: 'text-teal-600 dark:text-teal-400' },
        { label: 'Non-Teaching', value: stats().nonTeaching, active: categoryFilter === 'NON_TEACHING', cls: 'text-violet-600 dark:text-violet-400' },
      ] as chip}
        <button
          onclick={() => categoryFilter = chip.active && categoryFilter ? '' : (chip.label === 'Total' ? '' : chip.label === 'Teaching' ? 'TEACHING' : 'NON_TEACHING')}
          class="flex items-baseline gap-1.5 rounded-xl border px-3.5 py-2 transition
                 {chip.active
                   ? 'border-[var(--brand)] bg-[var(--brand-dim)]'
                   : 'border-[var(--border)] bg-[var(--card)] hover:bg-[var(--hover)]'}">
          <span class="text-base font-bold {chip.cls}">{chip.value}</span>
          <span class="text-xs text-[var(--fg-muted)]">{chip.label}</span>
        </button>
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
      <input bind:value={search} placeholder="Search name, ID, position…"
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
  </div>

  <!-- Table -->
  {#if $query.isPending}
    <div class="space-y-2">
      {#each [1,2,3,4,5] as _}
        <div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>
      {/each}
    </div>
  {:else if $query.isError}
    <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40
                p-4 text-sm text-red-600 dark:text-red-400">
      Could not load staff list.
      <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
    </div>
  {:else if filtered().length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">
        {search || genderFilter || categoryFilter ? 'No staff match your filters.' : 'No staff on record yet.'}
      </p>
      {#if search || genderFilter || categoryFilter}
        <button onclick={() => { search = ''; genderFilter = ''; categoryFilter = ''; }}
          class="mt-2 text-sm font-medium transition hover:underline" style="color: var(--brand)">
          Clear filters
        </button>
      {/if}
    </div>
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
          {#each filtered() as s (s.id)}
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
                    <div class="mt-0.5 flex items-center gap-1.5 flex-wrap">
                      <span class="text-xs text-[var(--fg-muted)]">{s.staff_number}</span>
                      {#if s.staff_category}
                        <span class="rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide
                                     {CAT_STYLE[s.staff_category] ?? ''}">
                          {CAT_LABEL[s.staff_category] ?? s.staff_category}
                        </span>
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
                <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold
                             {s.is_active
                               ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
                               : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}">
                  {s.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

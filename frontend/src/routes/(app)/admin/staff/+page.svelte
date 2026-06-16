<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { listStaff, type StaffSummary } from '$lib/api/staff';
  import StaffForm from './StaffForm.svelte';

  let activeOnly  = $state(true);
  let search      = $state('');
  let deptFilter  = $state('');
  let genderFilter = $state('');
  let showForm    = $state(false);

  const query = createQuery({
    queryKey: ['staff', activeOnly],
    queryFn:  () => listStaff({ active_only: activeOnly }),
    staleTime: 2 * 60_000,
  });

  const depts = $derived(() => {
    const s = new Set<string>();
    for (const m of $query.data ?? []) if (m.department) s.add(m.department);
    return [...s].sort();
  });

  const filtered = $derived(() => {
    let list: StaffSummary[] = $query.data ?? [];
    const q = search.trim().toLowerCase();
    if (q)           list = list.filter(s =>
      s.display_name.toLowerCase().includes(q) ||
      s.staff_number.toLowerCase().includes(q) ||
      (s.position_name ?? '').toLowerCase().includes(q) ||
      (s.department ?? '').toLowerCase().includes(q)
    );
    if (deptFilter)   list = list.filter(s => s.department === deptFilter);
    if (genderFilter) list = list.filter(s => s.gender === genderFilter);
    return list;
  });

  const total = $derived(() => ($query.data ?? []).length);

  function exportCSV() {
    const rows = filtered();
    if (!rows.length) return;
    const esc = (v: string | null | undefined) => `"${(v ?? '').replace(/"/g, '""')}"`;
    const header = ['Name','Staff No.','Position','Department','Gender','Phone','Email','Joined','Status'];
    const lines = [
      header.join(','),
      ...rows.map(s => [
        esc(s.display_name), esc(s.staff_number), esc(s.position_name),
        esc(s.department), s.gender ?? '', s.phone ?? '', s.email ?? '',
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
</script>

<div class="space-y-5">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold text-[var(--fg)]">Staff</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
        {#if filtered().length !== total()}
          Showing {filtered().length} of {total()} member{total() !== 1 ? 's' : ''}
        {:else}
          {total()} member{total() !== 1 ? 's' : ''} on record
        {/if}
      </p>
    </div>
    <div class="flex gap-2">
      <button onclick={exportCSV} disabled={!filtered().length}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:text-[var(--fg)] hover:bg-[var(--hover)] disabled:opacity-40">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/>
        </svg>
        Export CSV
      </button>
      <button onclick={() => { showForm = !showForm; }}
        class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-90"
        style="background-color: var(--brand)">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add staff
      </button>
    </div>
  </div>

  {#if showForm}
    <StaffForm
      onSuccess={(staff) => { showForm = false; goto(`/admin/staff/${staff.id}`); }}
      onCancel={() => showForm = false}
    />
  {/if}

  <!-- Filter bar -->
  <div class="flex flex-wrap gap-2">
    <div class="relative min-w-48 flex-1">
      <svg class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
           fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" d="m21 21-4.35-4.35"/>
      </svg>
      <input bind:value={search} placeholder="Search name, ID, position…"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2.5 pl-9 pr-4 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
    </div>
    <select bind:value={deptFilter}
      class="h-10 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
      <option value="">All departments</option>
      {#each depts() as d}<option value={d}>{d}</option>{/each}
    </select>
    <select bind:value={genderFilter}
      class="h-10 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
      <option value="">All genders</option>
      <option value="MALE">Male</option>
      <option value="FEMALE">Female</option>
    </select>
    <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--fg-muted)]">
      <input type="checkbox" bind:checked={activeOnly} class="accent-[var(--brand)] rounded" />
      Active only
    </label>
  </div>

  <!-- Table -->
  {#if $query.isPending}
    <div class="space-y-2">
      {#each [1,2,3,4,5] as _}
        <div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>
      {/each}
    </div>
  {:else if $query.isError}
    <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-4 text-sm text-red-600 dark:text-red-400">
      Could not load staff list.
      <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
    </div>
  {:else if filtered().length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">
        {search || deptFilter || genderFilter ? 'No staff match your filters.' : 'No staff on record yet.'}
      </p>
      {#if search || deptFilter || genderFilter}
        <button onclick={() => { search = ''; deptFilter = ''; genderFilter = ''; }}
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
                class="cursor-pointer transition hover:bg-[var(--hover)]">
              <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                  <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
                       style="background-color: {GENDER_BG[s.gender ?? ''] ?? 'var(--brand)'}">
                    {initials(s)}
                  </div>
                  <div>
                    <p class="font-semibold text-[var(--fg)]">{s.display_name}</p>
                    <p class="text-xs text-[var(--fg-muted)]">{s.staff_number}{s.department ? ' · ' + s.department : ''}</p>
                  </div>
                </div>
              </td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{s.position_name ?? '—'}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] lg:table-cell">{s.phone ?? s.email ?? '—'}</td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold
                             {s.is_active ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
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

<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listStaffPage, listCategories, type StaffSummary, type StaffListParams, type StaffListPage } from '$lib/api/staff';
  import StaffForm        from './StaffForm.svelte';
  import StaffImportModal from './StaffImportModal.svelte';
  import StaffFilterBar   from './StaffFilterBar.svelte';
  import Badge            from '$lib/components/Badge.svelte';
  import EmptyState       from '$lib/components/EmptyState.svelte';
  import CustomExportModal from '$lib/components/CustomExportModal.svelte';
  import Pagination        from '$lib/components/Pagination.svelte';
  import ActionMenu        from '$lib/components/ActionMenu.svelte';
  import { setPageTitle } from '$lib/stores/title';

  setPageTitle('Staff');
  const PAGE_SIZE = 50;

  let drawerOpen   = $state(false);
  let importOpen   = $state(false);
  let activeOnly   = $state(true);
  let genderFilter = $state<'' | 'MALE' | 'FEMALE'>('');
  let jobFilter    = $state(''); // category_id
  let page         = $state(1);

  // Search: local state for responsive input; debounced into the backend query
  let searchInput = $state('');
  let search      = $state('');
  $effect(() => {
    const val = searchInput;
    const t = setTimeout(() => { search = val; page = 1; }, 300);
    return () => clearTimeout(t);
  });

  const hasFilters = $derived(!!(search || genderFilter || jobFilter));

  const params = $derived<StaffListParams>({
    active_only: activeOnly,
    skip:        (page - 1) * PAGE_SIZE,
    limit:       PAGE_SIZE,
    search:      search || undefined,
    gender:      genderFilter || undefined,
    category_id: jobFilter || undefined,
  });

  const query = reactiveQuery<StaffListPage>(() => ({
    queryKey: ['staff', params] as const,
    queryFn:  () => listStaffPage(params),
    staleTime: 2 * 60_000,
  }));

  const staffList = $derived<StaffSummary[]>($query.data?.items ?? []);
  const total     = $derived<number>($query.data?.total ?? 0);

  // Reset to page 1 whenever a filter changes (deliberately NOT depending on
  // `params`/`page` itself — that would reset page 1 on every page navigation too).
  $effect(() => { activeOnly; genderFilter; jobFilter; search; page = 1; });

  const categoriesQ = createQuery({ queryKey: ['staff-categories'], queryFn: listCategories, staleTime: 5 * 60_000 });

  let customExportOpen = $state(false);

  const exportFilterParams = $derived({
    active_only: activeOnly,
    search:      search || undefined,
    gender:      genderFilter || undefined,
    category_id: jobFilter || undefined,
  });

  function clearFilters() {
    searchInput = ''; search = ''; genderFilter = ''; jobFilter = '';
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
        {total} member{total !== 1 ? 's' : ''}{hasFilters ? ' matching filters' : ' on record'}
      </p>
    </div>
    <div class="flex items-center gap-2">
      <ActionMenu actions={[
        { label: 'Export', onClick: () => customExportOpen = true,
          icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/>' },
        { label: 'Import', onClick: () => importOpen = true,
          icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>' },
      ]} />
      <button onclick={() => drawerOpen = true} class="btn-primary">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add staff
      </button>
    </div>
  </div>

  <StaffFilterBar
    {searchInput} onSearchInput={(v) => searchInput = v}
    {genderFilter} onGenderChange={(v) => genderFilter = v as typeof genderFilter}
    {jobFilter} onJobChange={(v) => jobFilter = v}
    {activeOnly} onActiveOnlyChange={(v) => activeOnly = v}
    categories={$categoriesQ.data ?? []}
    total={total} isPending={$query.isPending} {hasFilters}
    onClearFilters={clearFilters}
  />

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
  {:else if staffList.length === 0}
    <EmptyState
      iconPath="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
      title={hasFilters ? 'No staff match your filters.' : 'No staff on record yet.'}
      description={hasFilters
        ? 'Try adjusting or clearing your search and filters.'
        : 'Add your first staff member to get started.'}
      action={hasFilters ? clearFilters : () => { drawerOpen = true; }}
      actionLabel={hasFilters ? 'Clear filters' : 'Add first staff member'}
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
          {#each staffList as s (s.id)}
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
    <div class="mt-4">
      <Pagination total={total} pageSize={PAGE_SIZE} {page} label="staff" onPageChange={(p) => page = p} />
    </div>
  {/if}
</div>

{#if customExportOpen}
  <CustomExportModal
    entityType="staff"
    filterParams={exportFilterParams}
    onClose={() => customExportOpen = false}
  />
{/if}

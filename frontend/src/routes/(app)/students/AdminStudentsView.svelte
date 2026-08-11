<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listStudentsPage, type StudentSummary, type StudentListParams, type StudentListPage } from '$lib/api/students';
  import { listClasses } from '$lib/api/academic';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import StudentForm         from './StudentForm.svelte';
  import StudentImportDrawer from './StudentImportDrawer.svelte';
  import StudentTable        from './StudentTable.svelte';
  import StudentFilterBar    from './StudentFilterBar.svelte';
  import BulkActionModal     from './BulkActionModal.svelte';
  import EmptyState          from '$lib/components/EmptyState.svelte';
  import PageHeader          from '$lib/components/PageHeader.svelte';
  import CustomExportModal   from '$lib/components/CustomExportModal.svelte';
  import Pagination          from '$lib/components/Pagination.svelte';

  const PAGE_SIZE = 50;

  // ── URL-based filter state ──────────────────────────────────────────────────
  // class, year, gender, active are persisted in the URL.
  // year encodes "level::year_group" e.g. "B::3" or "KG::1".
  const sp      = $derived($page.url.searchParams);
  const classId = $derived(sp.get('class')  ?? '');
  const yearKey = $derived(sp.get('year')   ?? '');   // e.g. "B::3"
  const gender  = $derived((sp.get('gender') ?? '') as 'MALE' | 'FEMALE' | '');
  const activeOnly = $derived(sp.get('active') !== 'false');
  const graduated  = $derived(sp.get('graduated') === 'true');
  const pageNum = $derived(Math.max(1, Number(sp.get('page')) || 1));

  // Most graduated students are is_active=false — selecting "Graduated" must
  // force active=false in the same click, or the list shows zero results.
  function toggleGraduated() {
    const url = new URL($page.url);
    if (graduated) {
      url.searchParams.delete('graduated');
    } else {
      url.searchParams.set('graduated', 'true');
      url.searchParams.set('active', 'false');
    }
    url.searchParams.delete('page');
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  // Parse yearKey → { level, year_group } for the API
  const yearFilter = $derived.by(() => {
    if (!yearKey) return { level: undefined, year_group: undefined };
    const [lvl, yg] = yearKey.split('::');
    return { level: lvl || undefined, year_group: yg ? Number(yg) : undefined };
  });

  function setFilter(key: string, value: string) {
    const url = new URL($page.url);
    if (value) url.searchParams.set(key, value);
    else       url.searchParams.delete(key);
    if (key === 'year') url.searchParams.delete('class'); // year change resets class drill-down
    if (key !== 'page') url.searchParams.delete('page');  // any filter change invalidates the current page
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  function goToPage(p: number) { setFilter('page', p > 1 ? String(p) : ''); }

  // Search: local state for responsive input; synced to URL with 300ms debounce
  let searchInput = $state(sp.get('q') ?? '');
  $effect(() => {
    const fromUrl = $page.url.searchParams.get('q') ?? '';
    if (fromUrl !== searchInput) searchInput = fromUrl;   // back/forward sync
  });
  $effect(() => {
    const val = searchInput;
    const t = setTimeout(() => setFilter('q', val), 300);
    return () => clearTimeout(t);
  });

  const hasFilters = $derived(!!(searchInput || gender || classId || yearKey || graduated));

  function clearFilters() {
    searchInput = '';
    const url = new URL($page.url);
    ['q', 'class', 'year', 'gender', 'graduated', 'page'].forEach(k => url.searchParams.delete(k));
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  // ── Sort — server-side, feeds into `params` below ────────────────────────────
  let sortCol = $state<'name' | 'admission' | 'class'>('name');
  let sortDir = $state<'asc' | 'desc'>('asc');

  function toggleSort(col: typeof sortCol) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
    goToPage(1); // new order — start back at the top
  }

  // ── Queries ─────────────────────────────────────────────────────────────────
  const params = $derived<StudentListParams>({
    active_only: activeOnly,
    skip:        (pageNum - 1) * PAGE_SIZE,
    limit:       PAGE_SIZE,
    sort_by:     sortCol,
    sort_dir:    sortDir,
    search:      ($page.url.searchParams.get('q') ?? '').trim() || undefined,
    gender:      gender    || undefined,
    class_id:    classId   || undefined,
    // When a specific class is chosen it already implies the year — skip the broader filter
    level:       classId ? undefined : yearFilter.level,
    year_group:  classId ? undefined : yearFilter.year_group,
    graduated:   graduated || undefined,
  });

  const studentsQ = reactiveQuery<StudentListPage>(() => ({
    queryKey: ['students', params] as const,
    queryFn:  () => listStudentsPage(params),
    staleTime: 60_000,
  }));

  const classesQ = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 5 * 60_000 });

  // ── Derived data ─────────────────────────────────────────────────────────────
  const students = $derived<StudentSummary[]>($studentsQ.data?.items ?? []);
  const total    = $derived<number>($studentsQ.data?.total ?? 0);

  // Unique (level, year_group) pairs — the year dropdown options.
  const yearOptions = $derived.by(() => {
    const seen = new Set<string>();
    const opts: { key: string; label: string }[] = [];
    for (const c of ($classesQ.data ?? [])) {
      const key = `${c.level}::${c.year_group}`;
      if (!seen.has(key)) {
        seen.add(key);
        opts.push({ key, label: c.level.toUpperCase() === 'CRECHE' ? c.level : `${c.level} ${c.year_group}` });
      }
    }
    return opts.sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  });

  // Class dropdown narrows to the selected year when one is active.
  const filteredClasses = $derived.by(() => {
    const all = $classesQ.data ?? [];
    if (!yearKey) return all;
    const [lvl, yg] = yearKey.split('::');
    return all.filter(c => c.level === lvl && c.year_group === Number(yg));
  });


  // ── Selection ────────────────────────────────────────────────────────────────
  let selected = $state(new Set<string>());
  const allSelected = $derived(students.length > 0 && selected.size === students.length);
  function toggleAll()        { selected = allSelected ? new Set() : new Set(students.map(s => s.id)); }
  function toggle(id: string) { const n = new Set(selected); n.has(id) ? n.delete(id) : n.add(id); selected = n; }
  $effect(() => { params; selected = new Set(); });

  // ── Export ───────────────────────────────────────────────────────────────────
  let formOpen         = $state(false);
  let importOpen       = $state(false);
  let customExportOpen = $state(false);
</script>

<PageHeader
  title="Students"
  description={$isSchoolAdmin ? 'Manage enrolment, guardians, and student records.' : 'Students assigned to your classes or house.'}
>
  {#if $isSchoolAdmin}
    <button onclick={() => importOpen = true} class="btn-ghost">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
      Import
    </button>
    <button onclick={() => customExportOpen = true} class="btn-ghost">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
      Export
    </button>
    <button onclick={() => formOpen = true} class="btn-primary">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
      Add student
    </button>
  {/if}
</PageHeader>

<StudentFilterBar
  {searchInput} onSearchInput={(v) => searchInput = v}
  {yearKey} {classId} {gender} {activeOnly} {graduated}
  {yearOptions} {filteredClasses}
  total={total} isPending={$studentsQ.isPending} {hasFilters}
  {setFilter} onToggleGraduated={toggleGraduated} onClearFilters={clearFilters}
/>

<!-- Table states -->
{#if $studentsQ.isPending}
  <div class="space-y-2">
    {#each [1,2,3,4,5] as _}
      <div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>
    {/each}
  </div>
{:else if $studentsQ.isError}
  <div class="rounded-xl border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
    Could not load students. <button onclick={() => $studentsQ.refetch()} class="ml-1 underline">Retry</button>
  </div>
{:else if students.length === 0}
  <EmptyState
    iconPath="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
    title={hasFilters ? 'No students match your filters' : 'No students yet'}
    description={hasFilters ? 'Try adjusting or clearing the filters.' : 'Import from a spreadsheet or add students one by one.'}
    actionLabel={!hasFilters ? 'Add student' : undefined}
    action={!hasFilters ? () => formOpen = true : undefined}
    secondaryActionLabel={!hasFilters ? 'Import' : undefined}
    secondaryAction={!hasFilters ? () => importOpen = true : undefined}
  />
{:else}
  <StudentTable
    {students}
    {selected} {allSelected}
    isAdmin={$isSchoolAdmin}
    {sortCol} {sortDir}
    onSort={toggleSort}
    onToggle={toggle}
    onToggleAll={toggleAll}
  />
  <div class="mt-4">
    <Pagination total={total} pageSize={PAGE_SIZE} page={pageNum} label="students" onPageChange={goToPage} />
  </div>
{/if}

{#if $isSchoolAdmin}
  <BulkActionModal {selected} classes={$classesQ.data ?? []} onClear={() => selected = new Set()} />
  <StudentForm open={formOpen} onClose={() => formOpen = false} />
  <StudentImportDrawer open={importOpen} onClose={() => importOpen = false} />
  {#if customExportOpen}
    <CustomExportModal entityType="students" filterParams={{ ...params }} onClose={() => customExportOpen = false} />
  {/if}
{/if}

<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listStudents, exportStudentsCsv, type StudentSummary, type StudentListParams } from '$lib/api/students';
  import { listClasses } from '$lib/api/academic';
  import { school } from '$lib/stores/school';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import { setPageTitle } from '$lib/stores/title';
  import StudentForm         from './StudentForm.svelte';
  import StudentImportDrawer from './StudentImportDrawer.svelte';
  import StudentTable        from './StudentTable.svelte';
  import BulkActionModal     from './BulkActionModal.svelte';
  import EmptyState          from '$lib/components/EmptyState.svelte';
  import PageHeader          from '$lib/components/PageHeader.svelte';
  import CustomExportModal   from '$lib/components/CustomExportModal.svelte';
  setPageTitle('Students');

  // ── URL-based filter state ──────────────────────────────────────────────────
  // class, level, gender, active are persisted in the URL so users can bookmark
  // and share filtered views. Search is local (debounced to URL).
  const sp       = $derived($page.url.searchParams);
  const classId  = $derived(sp.get('class')  ?? '');
  const level    = $derived(sp.get('level')  ?? '');
  const gender   = $derived((sp.get('gender') ?? '') as 'MALE' | 'FEMALE' | '');
  const activeOnly = $derived(sp.get('active') !== 'false');

  function setFilter(key: string, value: string) {
    const url = new URL($page.url);
    if (value) url.searchParams.set(key, value);
    else       url.searchParams.delete(key);
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

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

  const hasFilters = $derived(!!(searchInput || gender || classId || level));

  function clearFilters() {
    searchInput = '';
    const url = new URL($page.url);
    ['q', 'class', 'level', 'gender'].forEach(k => url.searchParams.delete(k));
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  // ── Queries ─────────────────────────────────────────────────────────────────
  const params = $derived<StudentListParams>({
    active_only: activeOnly,
    limit:       200,
    search:      ($page.url.searchParams.get('q') ?? '').trim() || undefined,
    gender:      gender   || undefined,
    class_id:    classId  || undefined,
    level:       level    || undefined,
  });

  const studentsQ = reactiveQuery(() => ({
    queryKey: ['students', params] as const,
    queryFn:  () => listStudents(params),
    staleTime: 60_000,
  }));

  const classesQ = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 5 * 60_000 });

  // ── Derived data ─────────────────────────────────────────────────────────────
  const students = $derived<StudentSummary[]>($studentsQ.data ?? []);
  const levels   = $derived([...new Set(($classesQ.data ?? []).map(c => c.level))].sort());

  // Boarding stat only meaningful for boarding school types
  const showBoardingStat = $derived(['SHS', 'TECHNICAL', 'VOCATIONAL'].includes($school?.schoolType ?? ''));
  const stats = $derived.by(() => ({
    total:    students.length,
    male:     students.filter(s => s.gender === 'MALE').length,
    female:   students.filter(s => s.gender === 'FEMALE').length,
    boarding: students.filter(s => s.is_boarding).length,
  }));

  // ── Client-side sort ─────────────────────────────────────────────────────────
  let sortCol = $state<'name' | 'admission' | 'class'>('name');
  let sortDir = $state<'asc' | 'desc'>('asc');

  function toggleSort(col: typeof sortCol) {
    if (sortCol === col) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    else { sortCol = col; sortDir = 'asc'; }
  }

  const sorted = $derived.by(() => {
    const arr = [...students];
    return arr.sort((a, b) => {
      const va = sortCol === 'name'      ? (a.display_name       ?? '')
               : sortCol === 'admission' ? (a.admission_number   ?? '')
               :                          (a.current_class_name  ?? '');
      const vb = sortCol === 'name'      ? (b.display_name       ?? '')
               : sortCol === 'admission' ? (b.admission_number   ?? '')
               :                          (b.current_class_name  ?? '');
      return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    });
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
  let exporting        = $state(false);
  let customExportOpen = $state(false);
  let exportMenuOpen   = $state(false);

  async function handleExport() {
    exporting = true;
    try {
      const blob = await exportStudentsCsv(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'students.csv';
      a.click(); URL.revokeObjectURL(url);
    } finally { exporting = false; }
  }

  const selClass = 'rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
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
    <div class="relative">
      <button onclick={() => exportMenuOpen = !exportMenuOpen} disabled={exporting} class="btn-ghost">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
        {exporting ? 'Exporting…' : 'Export'}
      </button>
      {#if exportMenuOpen}
        <button class="fixed inset-0 z-[5] cursor-default" onclick={() => exportMenuOpen = false} tabindex="-1" aria-hidden="true"></button>
        <div class="absolute right-0 top-full z-10 mt-1 w-44 rounded-xl border border-[var(--border)] bg-[var(--card)] py-1 shadow-lg">
          <button onclick={() => { exportMenuOpen = false; handleExport(); }} class="w-full px-4 py-2 text-left text-sm text-[var(--fg)] hover:bg-[var(--hover)]">Full export (CSV)</button>
          <button onclick={() => { exportMenuOpen = false; customExportOpen = true; }} class="w-full px-4 py-2 text-left text-sm text-[var(--fg)] hover:bg-[var(--hover)]">Custom export…</button>
        </div>
      {/if}
    </div>
    <button onclick={() => formOpen = true} class="btn-primary">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
      Add student
    </button>
  {/if}
</PageHeader>

<!-- Stats row — boarding only for boarding-school types -->
<div class="mb-5 grid grid-cols-2 gap-3 {showBoardingStat ? 'sm:grid-cols-4' : 'sm:grid-cols-3'}">
  {#each [
    { label: 'Total',    value: stats.total,    color: 'text-[var(--fg)]' },
    { label: 'Male',     value: stats.male,     color: 'text-blue-600 dark:text-blue-400' },
    { label: 'Female',   value: stats.female,   color: 'text-pink-600 dark:text-pink-400' },
    ...(showBoardingStat ? [{ label: 'Boarding', value: stats.boarding, color: 'text-amber-600 dark:text-amber-400' }] : []),
  ] as stat}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
      <p class="text-xs font-medium text-[var(--fg-muted)]">{stat.label}</p>
      <p class="mt-1 text-2xl font-bold {stat.color}">{$studentsQ.isPending ? '—' : stat.value}</p>
    </div>
  {/each}
</div>

<!-- Filters + result count -->
<div class="mb-4 flex flex-wrap items-center gap-2">
  <div class="relative min-w-48 flex-1">
    <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
         fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/>
    </svg>
    <input bind:value={searchInput} placeholder="Search name or admission no…"
      class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2 pl-9 pr-4
             text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
             focus:border-[var(--brand)] focus:outline-none transition" />
  </div>

  <select value={classId} onchange={(e) => setFilter('class', e.currentTarget.value)} class={selClass}>
    <option value="">All classes</option>
    {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
  </select>

  <select value={level} onchange={(e) => setFilter('level', e.currentTarget.value)} class={selClass}>
    <option value="">All levels</option>
    {#each levels as l}<option value={l}>{l}</option>{/each}
  </select>

  <div class="flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1">
    {#each [['', 'All'], ['MALE', 'Boys'], ['FEMALE', 'Girls']] as [val, label]}
      <button onclick={() => setFilter('gender', val === gender ? '' : val as string)}
        class="rounded-lg px-3 py-1 text-xs font-semibold transition
               {gender === val ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
        {label}
      </button>
    {/each}
  </div>

  <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
    <input type="checkbox" checked={activeOnly} onchange={(e) => setFilter('active', e.currentTarget.checked ? '' : 'false')} class="accent-[var(--brand)]" />
    Active only
  </label>

  <!-- Result count — live, near filters so users see impact immediately -->
  {#if !$studentsQ.isPending}
    <span class="rounded-lg border border-[var(--border)] bg-[var(--hover)] px-2.5 py-1.5 text-xs font-semibold tabular-nums text-[var(--fg-muted)]">
      {students.length} student{students.length !== 1 ? 's' : ''}
    </span>
  {/if}

  {#if hasFilters}
    <button onclick={clearFilters} class="text-xs text-[var(--fg-muted)] underline hover:text-[var(--fg)] transition">
      Clear filters
    </button>
  {/if}
</div>

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
{:else if sorted.length === 0}
  <EmptyState
    iconPath="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
    title={hasFilters ? 'No students match your filters' : 'No students yet'}
    description={hasFilters ? 'Try adjusting or clearing the filters.' : 'Import from a spreadsheet or add students one by one.'}
    actionLabel={!hasFilters ? 'Add student' : undefined}
    action={!hasFilters ? () => formOpen = true : undefined}
  />
{:else}
  <StudentTable
    students={sorted}
    {selected} {allSelected}
    isAdmin={$isSchoolAdmin}
    {sortCol} {sortDir}
    onSort={toggleSort}
    onToggle={toggle}
    onToggleAll={toggleAll}
  />
{/if}

{#if $isSchoolAdmin}
  <BulkActionModal {selected} classes={$classesQ.data ?? []} onClear={() => selected = new Set()} />
  <StudentForm open={formOpen} onClose={() => formOpen = false} />
  <StudentImportDrawer open={importOpen} onClose={() => importOpen = false} />
  {#if customExportOpen}
    <CustomExportModal entityType="students" filterParams={params} onClose={() => customExportOpen = false} />
  {/if}
{/if}

<script lang="ts">
  import { goto } from '$app/navigation';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listStudentsPage, type StudentSummary, type StudentListParams, type StudentListPage } from '$lib/api/students';
  import StudentTable from './StudentTable.svelte';
  import EmptyState   from '$lib/components/EmptyState.svelte';
  import PageHeader   from '$lib/components/PageHeader.svelte';
  import Pagination   from '$lib/components/Pagination.svelte';

  const PAGE_SIZE = 50;

  // Deliberately no year/class/graduated filters and no URL persistence — a
  // class teacher's own roster (already server-scoped to their ClassTeacher/
  // SubjectTeacher assignments, services/student_list.py) is small enough
  // that the admin page's full toolset would just be clutter. See the
  // teacher/admin students-page split plan for the full rationale.
  let searchInput = $state('');
  let gender      = $state<'MALE' | 'FEMALE' | ''>('');
  let activeOnly  = $state(true);
  let page        = $state(1);

  let debouncedSearch = $state('');
  $effect(() => {
    const val = searchInput;
    const t = setTimeout(() => debouncedSearch = val, 300);
    return () => clearTimeout(t);
  });
  $effect(() => { debouncedSearch; gender; activeOnly; page = 1; });

  const hasFilters = $derived(!!(searchInput || gender || !activeOnly));
  function clearFilters() { searchInput = ''; gender = ''; activeOnly = true; }

  const params = $derived<StudentListParams>({
    active_only: activeOnly,
    skip:  (page - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    sort_by: 'name',
    sort_dir: 'asc',
    search: debouncedSearch.trim() || undefined,
    gender: gender || undefined,
  });

  const studentsQ = reactiveQuery<StudentListPage>(() => ({
    queryKey: ['my-students', params] as const,
    queryFn:  () => listStudentsPage(params),
    staleTime: 60_000,
  }));

  const students = $derived<StudentSummary[]>($studentsQ.data?.items ?? []);
  const total    = $derived<number>($studentsQ.data?.total ?? 0);
</script>

<PageHeader title="My Students" description="Students in the class(es) you teach." />

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

  <div class="flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1">
    {#each [['', 'All'], ['MALE', 'Boys'], ['FEMALE', 'Girls']] as [val, label]}
      <button onclick={() => gender = val as typeof gender}
        class="rounded-lg px-3 py-1 text-xs font-semibold transition
               {gender === val ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
        {label}
      </button>
    {/each}
  </div>

  <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
    <input type="checkbox" bind:checked={activeOnly} class="accent-[var(--brand)]" />
    Active only
  </label>

  {#if !$studentsQ.isPending}
    <span class="rounded-lg border border-[var(--border)] bg-[var(--hover)] px-2.5 py-1.5 text-xs font-semibold tabular-nums text-[var(--fg-muted)]">
      {total} student{total !== 1 ? 's' : ''}
    </span>
  {/if}

  {#if hasFilters}
    <button onclick={clearFilters} class="text-xs text-[var(--fg-muted)] underline hover:text-[var(--fg)] transition">
      Clear filters
    </button>
  {/if}
</div>

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
    title={hasFilters ? 'No students match your filters' : 'No students in your classes yet'}
    description={hasFilters ? 'Try adjusting or clearing the filters.' : 'Once you’re assigned as a class or subject teacher, students will appear here.'}
  />
{:else}
  <StudentTable
    students={students}
    selected={new Set()}
    allSelected={false}
    isAdmin={false}
    sortCol="name"
    sortDir="asc"
    onSort={() => {}}
    onToggle={() => {}}
    onToggleAll={() => {}}
  />
  <div class="mt-4">
    <Pagination total={total} pageSize={PAGE_SIZE} page={page} label="students" onPageChange={(p) => page = p} />
  </div>
{/if}

<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { goto } from '$app/navigation';
  import {
    listStudents, exportStudentsCsv,
    type StudentSummary, type StudentListParams,
  } from '$lib/api/students';
  import { listClasses } from '$lib/api/academic';
  import StudentForm          from './StudentForm.svelte';
  import StudentImportDrawer  from './StudentImportDrawer.svelte';
  import BulkActionModal      from './BulkActionModal.svelte';
  import EmptyState           from '$lib/components/EmptyState.svelte';
  import PageHeader           from '$lib/components/PageHeader.svelte';

  // ── Filter state ────────────────────────────────────────────────────────────
  let search     = $state('');
  let activeOnly = $state(true);
  let gender     = $state<'MALE' | 'FEMALE' | ''>('');
  let classId    = $state('');
  let level      = $state('');

  // Derive query params reactively
  const params = $derived<StudentListParams>({
    active_only: activeOnly,
    limit: 200,
    search: search.trim() || undefined,
    gender: gender || undefined,
    class_id: classId || undefined,
    level: level || undefined,
  });

  // @tanstack/svelte-query v5 requires a Svelte store for reactive query options
  const queryOpts = writable({ queryKey: ['students', params] as const, queryFn: () => listStudents(params), staleTime: 60_000 });
  $effect(() => {
    const p = params;
    queryOpts.set({ queryKey: ['students', p] as const, queryFn: () => listStudents(p), staleTime: 60_000 });
  });
  const query = createQuery(queryOpts);

  const classesQ = createQuery({
    queryKey: ['classes'],
    queryFn:  listClasses,
    staleTime: 5 * 60_000,
  });

  // ── Derived stats ────────────────────────────────────────────────────────────
  const students = $derived.by(() => ($query.data ?? []) as StudentSummary[]);
  const stats = $derived.by(() => ({
    total:    students.length,
    male:     students.filter(s => s.gender === 'MALE').length,
    female:   students.filter(s => s.gender === 'FEMALE').length,
    boarding: students.filter(s => s.is_boarding).length,
  }));

  // Unique levels from classes list
  const levels = $derived(
    [...new Set(($classesQ.data ?? []).map(c => c.level))].sort()
  );

  // ── UI state ─────────────────────────────────────────────────────────────────
  let formOpen   = $state(false);
  let importOpen = $state(false);
  let exporting  = $state(false);

  // ── Selection ────────────────────────────────────────────────────────────────
  let selected   = $state(new Set<string>());

  const allSelected = $derived(students.length > 0 && selected.size === students.length);
  function toggleAll() { selected = allSelected ? new Set() : new Set(students.map(s => s.id)); }
  function toggle(id: string) { const n = new Set(selected); n.has(id) ? n.delete(id) : n.add(id); selected = n; }
  $effect(() => { students; selected = new Set(); });

  // ── Helpers ──────────────────────────────────────────────────────────────────
  function initials(s: StudentSummary) {
    return (s.first_name[0] + s.last_name[0]).toUpperCase();
  }

  function genderBadge(g: string | null) {
    if (g === 'MALE')   return 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300';
    if (g === 'FEMALE') return 'bg-pink-100 text-pink-700 dark:bg-pink-950/40 dark:text-pink-300';
    return 'hidden';
  }

  function clearFilters() {
    search = ''; gender = ''; classId = ''; level = '';
  }

  const hasFilters = $derived(!!(search || gender || classId || level));

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
</script>

<svelte:head><title>Students</title></svelte:head>

<PageHeader title="Students" description="Manage enrolment, guardians, and student records.">
  <button onclick={() => importOpen = true} class="btn-ghost">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
    Import
  </button>
  <button onclick={handleExport} disabled={exporting} class="btn-ghost">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
    {exporting ? 'Exporting…' : 'Export CSV'}
  </button>
  <button onclick={() => formOpen = true} class="btn-primary">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
    Add student
  </button>
</PageHeader>

<!-- Stats row -->
<div class="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
  {#each [
    { label: 'Total', value: stats.total, color: 'text-[var(--fg)]' },
    { label: 'Male',  value: stats.male,  color: 'text-blue-600 dark:text-blue-400' },
    { label: 'Female',value: stats.female,color: 'text-pink-600 dark:text-pink-400' },
    { label: 'Boarding',value: stats.boarding, color: 'text-amber-600 dark:text-amber-400' },
  ] as stat}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
      <p class="text-xs font-medium text-[var(--fg-muted)]">{stat.label}</p>
      <p class="mt-1 text-2xl font-bold {stat.color}">{$query.isPending ? '—' : stat.value}</p>
    </div>
  {/each}
</div>

<!-- Filters -->
<div class="mb-4 flex flex-wrap items-center gap-2">
  <div class="relative min-w-48 flex-1">
    <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
         fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/>
    </svg>
    <input bind:value={search} placeholder="Search name or admission no…"
      class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2 pl-9 pr-4 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none transition" />
  </div>

  <select bind:value={classId}
    class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition">
    <option value="">All classes</option>
    {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
  </select>

  <select bind:value={level}
    class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition">
    <option value="">All levels</option>
    {#each levels as l}<option value={l}>{l}</option>{/each}
  </select>

  <!-- Gender pills -->
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

  {#if hasFilters}
    <button onclick={clearFilters} class="text-xs text-[var(--fg-muted)] underline hover:text-[var(--fg)] transition">
      Clear filters
    </button>
  {/if}
</div>

<!-- Table -->
{#if $query.isPending}
  <div class="space-y-2">
    {#each [1,2,3,4,5] as _}
      <div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>
    {/each}
  </div>
{:else if $query.isError}
  <div class="rounded-xl border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
    Could not load students. Check your connection and refresh.
  </div>
{:else if students.length === 0}
  <EmptyState
    iconPath="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
    title={hasFilters ? 'No students match your filters' : 'No students yet'}
    description={hasFilters ? 'Try adjusting or clearing the filters.' : 'Import from a spreadsheet or add students one by one.'}
    actionLabel={!hasFilters ? 'Add student' : undefined}
    action={!hasFilters ? () => formOpen = true : undefined}
  />
{:else}
  <div class="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-[var(--border)] bg-[var(--hover)]">
          <th class="w-10 px-4 py-3">
            <input type="checkbox" checked={allSelected} onchange={toggleAll} class="rounded accent-[var(--brand)]" />
          </th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Student</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)] hidden sm:table-cell">Admission No.</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)] hidden md:table-cell">Class</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)] hidden lg:table-cell">Gender</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Status</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-[var(--border)]">
        {#each students as s (s.id)}
          <tr onclick={() => goto(`/students/${s.id}`)}
            class="cursor-pointer transition hover:bg-[var(--hover)] {selected.has(s.id) ? '!bg-[color-mix(in_srgb,var(--brand)_5%,transparent)]' : ''}">
            <td class="w-10 px-4 py-3" onclick={(e) => { e.stopPropagation(); toggle(s.id); }}>
              <input type="checkbox" checked={selected.has(s.id)} onchange={() => toggle(s.id)} class="rounded accent-[var(--brand)]" />
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-3">
                <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                     style="background: var(--brand)">{initials(s)}</div>
                <div>
                  <p class="font-medium text-[var(--fg)]">{s.display_name}</p>
                  <div class="flex flex-wrap items-center gap-1 sm:hidden">
                    <span class="font-mono text-xs text-[var(--fg-muted)]">{s.admission_number}</span>
                    {#if s.current_class_name}<span class="text-xs text-[var(--fg-subtle)]">· {s.current_class_name}</span>{/if}
                  </div>
                </div>
              </div>
            </td>
            <td class="px-4 py-3 font-mono text-xs text-[var(--fg-muted)] hidden sm:table-cell">{s.admission_number}</td>
            <td class="px-4 py-3 hidden md:table-cell">
              {#if s.current_class_name}
                <span class="rounded-lg bg-[var(--hover)] px-2 py-0.5 text-xs font-medium text-[var(--fg)]">{s.current_class_name}</span>
              {:else}
                <span class="text-xs text-[var(--fg-subtle)]">Not enrolled</span>
              {/if}
            </td>
            <td class="px-4 py-3 hidden lg:table-cell">
              {#if s.gender}
                <span class="inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase {genderBadge(s.gender)}">{s.gender}</span>
              {:else}<span class="text-xs text-[var(--fg-subtle)]">—</span>{/if}
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                {#if s.is_active}
                  <span class="inline-flex items-center gap-1 text-[10px] font-bold text-green-600 dark:text-green-500"><svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>Active</span>
                {:else}
                  <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--fg-muted)]">Inactive</span>
                {/if}
                {#if s.is_boarding}
                  <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400">Boarding</span>
                {/if}
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    <div class="border-t border-[var(--border)] px-4 py-2.5 text-xs text-[var(--fg-muted)]">
      Showing {students.length} student{students.length !== 1 ? 's' : ''}
    </div>
  </div>
{/if}

<BulkActionModal {selected} classes={$classesQ.data ?? []} onClear={() => selected = new Set()} />

<StudentForm open={formOpen} onClose={() => formOpen = false} />
<StudentImportDrawer open={importOpen} onClose={() => importOpen = false} />

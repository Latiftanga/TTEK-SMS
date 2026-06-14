<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listYears,
    listClasses,
    listSubjects,
    createClass,
    createSubject,
    assignSubjects,
    type AcademicYear,
    type SchoolClass,
    type Subject,
  } from '$lib/api/academic';

  const qc = useQueryClient();

  const yearsQuery = createQuery({
    queryKey: ['academic-years'],
    queryFn: listYears,
    staleTime: 5 * 60_000,
  });

  let selectedYearId = $state<string | null>(null);

  const currentYear = $derived(() =>
    ($yearsQuery.data ?? []).find((y: AcademicYear) => y.is_current) ?? ($yearsQuery.data ?? [])[0] ?? null
  );

  $effect(() => {
    if (!selectedYearId && currentYear()) {
      selectedYearId = currentYear()!.id;
    }
  });

  const classesQuery = createQuery({
    queryKey: ['classes', selectedYearId],
    queryFn: () => listClasses(selectedYearId!),
    enabled: !!selectedYearId,
    staleTime: 2 * 60_000,
  });

  const subjectsQuery = createQuery({
    queryKey: ['subjects'],
    queryFn: listSubjects,
    staleTime: 5 * 60_000,
  });

  let tab = $state<'classes' | 'subjects'>('classes');

  // Class form
  let showClassForm = $state(false);
  let classForm = $state({
    level: '',
    year_group: new Date().getFullYear(),
    stream: '',
    capacity: '',
  });
  let classError = $state('');

  // Subject form
  let showSubjectForm = $state(false);
  let subjectForm = $state({ code: '', name: '' });
  let subjectError = $state('');

  // Assign subjects to class
  let assigningClassId = $state<string | null>(null);
  let selectedSubjectIds = $state<Set<string>>(new Set());

  const createClassMut = createMutation({
    mutationFn: createClass,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes'] });
      showClassForm = false;
      classForm = { level: '', year_group: new Date().getFullYear(), stream: '', capacity: '' };
      classError = '';
    },
    onError: (e: unknown) => {
      classError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create class.';
    },
  });

  const createSubjectMut = createMutation({
    mutationFn: createSubject,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects'] });
      showSubjectForm = false;
      subjectForm = { code: '', name: '' };
      subjectError = '';
    },
    onError: (e: unknown) => {
      subjectError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create subject.';
    },
  });

  const assignSubjectsMut = createMutation({
    mutationFn: ({ classId, ids }: { classId: string; ids: string[] }) =>
      assignSubjects(classId, ids),
    onSuccess: () => {
      assigningClassId = null;
      selectedSubjectIds = new Set();
    },
  });

  const CLASS_LEVELS = [
    'Creche', 'Nursery 1', 'Nursery 2',
    'KG 1', 'KG 2',
    'Primary 1', 'Primary 2', 'Primary 3', 'Primary 4', 'Primary 5', 'Primary 6',
    'JHS 1', 'JHS 2', 'JHS 3',
    'SHS 1', 'SHS 2', 'SHS 3',
  ];

  function submitClass() {
    classError = '';
    if (!classForm.level) { classError = 'Level is required.'; return; }
    if (!selectedYearId) { classError = 'No year selected.'; return; }
    $createClassMut.mutate({
      academic_year_id: selectedYearId,
      level: classForm.level,
      year_group: Number(classForm.year_group),
      stream: classForm.stream || undefined,
      capacity: classForm.capacity ? Number(classForm.capacity) : undefined,
    });
  }

  function submitSubject() {
    subjectError = '';
    if (!subjectForm.code || !subjectForm.name) { subjectError = 'Code and name are required.'; return; }
    $createSubjectMut.mutate({ code: subjectForm.code.toUpperCase(), name: subjectForm.name });
  }

  function toggleSubject(id: string) {
    const next = new Set(selectedSubjectIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedSubjectIds = next;
  }

  function confirmAssign() {
    if (!assigningClassId) return;
    $assignSubjectsMut.mutate({ classId: assigningClassId, ids: [...selectedSubjectIds] });
  }
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold text-[var(--fg)]">Classes & Subjects</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">Organise your school structure</p>
    </div>
    <!-- Year selector -->
    <select
      bind:value={selectedYearId}
      class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
    >
      {#each ($yearsQuery.data ?? []) as y (y.id)}
        <option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>
      {/each}
    </select>
  </div>

  <!-- Tabs -->
  <div class="flex gap-1 rounded-xl bg-[var(--bg)] p-1 w-fit border border-[var(--border)]">
    {#each (['classes', 'subjects'] as const) as t}
      <button
        onclick={() => tab = t}
        class="rounded-lg px-4 py-2 text-sm font-medium transition
               {tab === t ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >
        {t === 'classes' ? 'Classes' : 'Subjects'}
      </button>
    {/each}
  </div>

  <!-- CLASSES tab -->
  {#if tab === 'classes'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button
          onclick={() => { showClassForm = !showClassForm; classError = ''; }}
          class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background-color: var(--brand)"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add class
        </button>
      </div>

      {#if showClassForm}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Class</h2>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Level</label>
              <select
                bind:value={classForm.level}
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
              >
                <option value="">Select level…</option>
                {#each CLASS_LEVELS as lvl}
                  <option value={lvl}>{lvl}</option>
                {/each}
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Year group</label>
              <input
                type="number"
                bind:value={classForm.year_group}
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Stream (optional)</label>
              <input
                bind:value={classForm.stream}
                placeholder="e.g. A, Gold"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Capacity (optional)</label>
              <input
                type="number"
                bind:value={classForm.capacity}
                placeholder="e.g. 40"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none"
              />
            </div>
          </div>
          {#if classError}
            <p class="mt-2 text-xs text-red-500">{classError}</p>
          {/if}
          <div class="mt-4 flex gap-2">
            <button
              onclick={submitClass}
              disabled={$createClassMut.isPending}
              class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background-color: var(--brand)"
            >
              {$createClassMut.isPending ? 'Creating…' : 'Create class'}
            </button>
            <button
              onclick={() => { showClassForm = false; classError = ''; }}
              class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]"
            >
              Cancel
            </button>
          </div>
        </div>
      {/if}

      {#if $classesQuery.isPending}
        <div class="space-y-2">
          {#each [1,2,3,4] as _}
            <div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>
          {/each}
        </div>
      {:else if !selectedYearId}
        <p class="text-sm text-[var(--fg-muted)]">Select an academic year to view classes.</p>
      {:else if ($classesQuery.data ?? []).length === 0}
        <div class="rounded-xl border border-dashed border-[var(--border)] p-7 text-center">
          <p class="text-sm text-[var(--fg-muted)]">No classes for this year yet.</p>
        </div>
      {:else}
        <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border)] text-left">
                <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Class</th>
                <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Year group</th>
                <th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Capacity</th>
                <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
                <th class="px-5 py-3"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--border)]">
              {#each ($classesQuery.data ?? []).sort((a: SchoolClass, b: SchoolClass) => a.display_name.localeCompare(b.display_name)) as cls (cls.id)}
                <tr class="group transition hover:bg-[var(--bg)]">
                  <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{cls.display_name}</td>
                  <td class="px-4 py-2.5 text-[var(--fg-muted)]">{cls.year_group}</td>
                  <td class="hidden px-5 py-2.5 text-[var(--fg-muted)] sm:table-cell">
                    {cls.capacity ?? '—'}
                  </td>
                  <td class="px-4 py-2.5">
                    <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold
                                 {cls.is_active
                                   ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
                                   : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}">
                      {cls.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td class="px-4 py-2.5 text-right">
                    <button
                      onclick={() => { assigningClassId = cls.id; selectedSubjectIds = new Set(); }}
                      class="text-xs font-medium text-[var(--fg-muted)] opacity-0 transition group-hover:opacity-100 hover:text-[var(--fg)]"
                    >
                      Assign subjects →
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

  <!-- SUBJECTS tab -->
  {:else}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button
          onclick={() => { showSubjectForm = !showSubjectForm; subjectError = ''; }}
          class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background-color: var(--brand)"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add subject
        </button>
      </div>

      {#if showSubjectForm}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Subject</h2>
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code</label>
              <input
                bind:value={subjectForm.code}
                placeholder="e.g. MATH"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
              <input
                bind:value={subjectForm.name}
                placeholder="e.g. Mathematics"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none"
              />
            </div>
          </div>
          {#if subjectError}
            <p class="mt-2 text-xs text-red-500">{subjectError}</p>
          {/if}
          <div class="mt-4 flex gap-2">
            <button
              onclick={submitSubject}
              disabled={$createSubjectMut.isPending}
              class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background-color: var(--brand)"
            >
              {$createSubjectMut.isPending ? 'Creating…' : 'Create subject'}
            </button>
            <button
              onclick={() => { showSubjectForm = false; subjectError = ''; }}
              class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]"
            >
              Cancel
            </button>
          </div>
        </div>
      {/if}

      {#if $subjectsQuery.isPending}
        <div class="space-y-2">
          {#each [1,2,3,4,5] as _}
            <div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>
          {/each}
        </div>
      {:else if ($subjectsQuery.data ?? []).length === 0}
        <div class="rounded-xl border border-dashed border-[var(--border)] p-7 text-center">
          <p class="text-sm text-[var(--fg-muted)]">No subjects yet.</p>
        </div>
      {:else}
        <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border)] text-left">
                <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Code</th>
                <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Name</th>
                <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--border)]">
              {#each ($subjectsQuery.data ?? []).sort((a: Subject, b: Subject) => a.name.localeCompare(b.name)) as subj (subj.id)}
                <tr class="transition hover:bg-[var(--bg)]">
                  <td class="px-4 py-2.5 font-mono text-xs text-[var(--fg-muted)]">{subj.code}</td>
                  <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{subj.name}</td>
                  <td class="px-4 py-2.5">
                    <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold
                                 {subj.is_active
                                   ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
                                   : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}">
                      {subj.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- Assign subjects drawer / modal -->
{#if assigningClassId}
  {@const cls = ($classesQuery.data ?? []).find((c: SchoolClass) => c.id === assigningClassId)}
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 backdrop-blur-sm sm:items-center"
       role="dialog" aria-modal="true">
    <div class="w-full max-w-md rounded-t-3xl sm:rounded-3xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h2 class="font-semibold text-[var(--fg)]">Assign subjects</h2>
          <p class="text-xs text-[var(--fg-muted)]">{cls?.display_name}</p>
        </div>
        <button
          onclick={() => { assigningClassId = null; selectedSubjectIds = new Set(); }}
          class="flex h-8 w-8 items-center justify-center rounded-full text-[var(--fg-muted)] transition hover:bg-[var(--bg)] hover:text-[var(--fg)]"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <div class="max-h-72 overflow-y-auto space-y-1.5 mb-4">
        {#each ($subjectsQuery.data ?? []).filter((s: Subject) => s.is_active) as subj (subj.id)}
          <button
            type="button"
            onclick={() => toggleSubject(subj.id)}
            class="flex w-full items-center gap-3 rounded-xl border px-4 py-2.5 text-left text-sm transition
                   {selectedSubjectIds.has(subj.id)
                     ? 'border-[var(--brand)] bg-[var(--brand)]/5 text-[var(--fg)]'
                     : 'border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border)] hover:text-[var(--fg)]'}"
          >
            <div class="flex h-4 w-4 shrink-0 items-center justify-center rounded border {selectedSubjectIds.has(subj.id) ? 'border-[var(--brand)]' : 'border-[var(--border)]'}"
                 style="{selectedSubjectIds.has(subj.id) ? 'background-color: var(--brand)' : ''}">
              {#if selectedSubjectIds.has(subj.id)}
                <svg class="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              {/if}
            </div>
            <span class="font-mono text-xs text-[var(--fg-muted)] w-12 shrink-0">{subj.code}</span>
            <span>{subj.name}</span>
          </button>
        {/each}
      </div>

      <div class="flex gap-2">
        <button
          onclick={confirmAssign}
          disabled={selectedSubjectIds.size === 0 || $assignSubjectsMut.isPending}
          class="flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
          style="background-color: var(--brand)"
        >
          {$assignSubjectsMut.isPending ? 'Assigning…' : `Assign ${selectedSubjectIds.size || ''} subject${selectedSubjectIds.size !== 1 ? 's' : ''}`}
        </button>
        <button
          onclick={() => { assigningClassId = null; selectedSubjectIds = new Set(); }}
          class="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
{/if}

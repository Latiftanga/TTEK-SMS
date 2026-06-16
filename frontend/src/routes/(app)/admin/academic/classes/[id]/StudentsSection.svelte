<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { type AcademicTerm, type SchoolClass } from '$lib/api/academic';
  import { listStudents, enrollStudent, bulkEnrollStudents, type StudentSummary } from '$lib/api/students';

  let { classId, terms, selectedTermId, classes }: {
    classId: string;
    terms: AcademicTerm[];
    selectedTermId: string;
    classes: SchoolClass[];
  } = $props();

  const qc = useQueryClient();

  const studentsQuery = createQuery(() => ({
    queryKey: ['class-students', classId, selectedTermId],
    queryFn: () => listStudents({ class_id: classId, term_id: selectedTermId, limit: 200 }),
    enabled: !!selectedTermId,
    staleTime: 60_000,
  }));
  const students = $derived<StudentSummary[]>($studentsQuery.data ?? []);

  let selected = $state(new Set<string>());
  const allSelected = $derived(students.length > 0 && selected.size === students.length);
  function toggleAll() { selected = allSelected ? new Set() : new Set(students.map(s => s.id)); }
  function toggle(id: string) { const n = new Set(selected); n.has(id) ? n.delete(id) : n.add(id); selected = n; }
  $effect(() => { selectedTermId; selected = new Set(); });

  let showEnroll   = $state(false);
  let enrollSearch = $state('');
  let enrollTermId = $state('');
  $effect(() => { if (showEnroll) enrollTermId = selectedTermId; });

  const searchQuery = createQuery(() => ({
    queryKey: ['student-search', enrollSearch],
    queryFn: () => listStudents({ search: enrollSearch, active_only: true, limit: 30 }),
    enabled: enrollSearch.trim().length >= 2,
    staleTime: 30_000,
  }));
  const searchResults = $derived<StudentSummary[]>($searchQuery.data ?? []);
  let enrollStudentId = $state('');

  const enrollMut = createMutation({
    mutationFn: () => enrollStudent({ student_id: enrollStudentId, class_id: classId, academic_term_id: enrollTermId }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['class-students'] }); showEnroll = false; enrollStudentId = ''; enrollSearch = ''; },
  });

  let bulkAction  = $state<'promote' | 'repeat' | 'demote' | null>(null);
  let bulkClassId = $state('');
  let bulkTermId  = $state('');
  let bulkError   = $state('');

  const bulkMut = createMutation({
    mutationFn: () => bulkEnrollStudents([...selected].map(sid => ({ student_id: sid, class_id: bulkClassId, academic_term_id: bulkTermId }))),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['class-students'] });
      bulkAction = null; selected = new Set(); bulkError = '';
      if (res.skipped) bulkError = `${res.enrolled} enrolled, ${res.skipped} already in a class for that term.`;
    },
    onError: (e: unknown) => { bulkError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.'; },
  });

  function openBulk(action: 'promote' | 'repeat' | 'demote') {
    bulkAction = action; bulkClassId = action === 'repeat' ? classId : ''; bulkTermId = ''; bulkError = '';
  }
</script>

<div>
  <div class="mb-4 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <h2 class="text-base font-semibold text-[var(--fg)]">Students</h2>
      {#if students.length > 0}
        <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-xs text-[var(--fg-muted)]">{students.length}</span>
      {/if}
    </div>
    <button
      onclick={() => showEnroll = true}
      disabled={!selectedTermId}
      class="h-8 rounded-lg bg-[var(--brand)] px-3 text-xs font-medium text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
    >+ Enroll</button>
  </div>

  {#if !selectedTermId}
    <p class="py-10 text-center text-sm text-[var(--fg-muted)]">Select a term above to view enrolled students.</p>
  {:else if $studentsQuery.isLoading}
    <p class="py-10 text-center text-sm text-[var(--fg-muted)]">Loading…</p>
  {:else if students.length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] py-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No students enrolled for this term.</p>
      <button onclick={() => showEnroll = true} class="mt-2 text-sm text-[var(--brand)] hover:underline">Enroll the first student</button>
    </div>
  {:else}
    <div class="overflow-x-auto rounded-xl border border-[var(--border)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] bg-[var(--hover)]">
            <th class="w-10 px-3 py-2.5"><input type="checkbox" checked={allSelected} onchange={toggleAll} class="rounded" /></th>
            <th class="px-4 py-2.5 text-left font-medium text-[var(--fg-muted)]">Name</th>
            <th class="px-4 py-2.5 text-left font-medium text-[var(--fg-muted)]">Admission #</th>
            <th class="px-4 py-2.5 text-left font-medium text-[var(--fg-muted)]">Gender</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each students as s}
            <tr class="bg-[var(--card)] transition-colors hover:bg-[var(--hover)] {selected.has(s.id) ? '!bg-[var(--hover)]' : ''}">
              <td class="px-3 py-2.5"><input type="checkbox" checked={selected.has(s.id)} onchange={() => toggle(s.id)} class="rounded" /></td>
              <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{s.display_name}</td>
              <td class="px-4 py-2.5 text-[var(--fg-muted)]">{s.admission_number}</td>
              <td class="px-4 py-2.5 text-[var(--fg-muted)]">{s.gender ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="mt-2 text-xs text-[var(--fg-muted)]">{students.length} student{students.length !== 1 ? 's' : ''}</p>
  {/if}
</div>

{#if selected.size > 0}
  <div class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2">
    <div class="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 shadow-xl">
      <span class="text-sm font-medium text-[var(--fg)]">{selected.size} selected</span>
      <div class="mx-2 h-4 w-px bg-[var(--border)]"></div>
      <button onclick={() => openBulk('promote')} class="rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--fg)] hover:bg-[var(--hover)]">Promote ↑</button>
      <button onclick={() => openBulk('repeat')}  class="rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--fg)] hover:bg-[var(--hover)]">Repeat ↺</button>
      <button onclick={() => openBulk('demote')}  class="rounded-lg px-3 py-1.5 text-sm font-medium text-[var(--fg)] hover:bg-[var(--hover)]">Demote ↓</button>
      <button onclick={() => selected = new Set()} class="ml-1 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]">✕</button>
    </div>
  </div>
{/if}

{#if showEnroll}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="mb-4 text-lg font-semibold text-[var(--fg)]">Enroll Student</h2>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Search student</span>
        <input bind:value={enrollSearch} placeholder="Name or admission number…"
          class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]" />
      </label>
      {#if searchResults.length > 0}
        <ul class="mt-2 max-h-44 overflow-y-auto divide-y divide-[var(--border)] rounded-lg border border-[var(--border)]">
          {#each searchResults as s}
            <li>
              <button onclick={() => { enrollStudentId = s.id; enrollSearch = s.display_name; }}
                class="w-full px-3 py-2 text-left text-sm hover:bg-[var(--hover)] {enrollStudentId === s.id ? 'bg-[var(--hover)] font-medium' : ''}">
                {s.display_name} · {s.admission_number}
              </button>
            </li>
          {/each}
        </ul>
      {/if}
      <label class="mt-3 block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Term</span>
        <select bind:value={enrollTermId} class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]">
          <option value="">— Select —</option>
          {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
        </select>
      </label>
      {#if $enrollMut.error}
        <p class="mt-2 text-xs text-red-500">{($enrollMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Error'}</p>
      {/if}
      <div class="mt-5 flex justify-end gap-3">
        <button onclick={() => { showEnroll = false; enrollStudentId = ''; enrollSearch = ''; }}
          class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
        <button onclick={() => $enrollMut.mutate()} disabled={!enrollStudentId || !enrollTermId || $enrollMut.isPending}
          class="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:opacity-90">
          {$enrollMut.isPending ? 'Enrolling…' : 'Enroll'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if bulkAction}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="mb-1 text-lg font-semibold capitalize text-[var(--fg)]">{bulkAction} Students</h2>
      <p class="mb-4 text-sm text-[var(--fg-muted)]">{selected.size} student{selected.size !== 1 ? 's' : ''} will be enrolled in the selected class and term.</p>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Target class</span>
        <select bind:value={bulkClassId} class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]">
          <option value="">— Select class —</option>
          {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
        </select>
      </label>
      <label class="mt-3 block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Target term</span>
        <select bind:value={bulkTermId} class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)]">
          <option value="">— Select term —</option>
          {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
        </select>
      </label>
      {#if bulkError}<p class="mt-2 text-xs text-amber-600">{bulkError}</p>{/if}
      <div class="mt-5 flex justify-end gap-3">
        <button onclick={() => bulkAction = null} class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
        <button onclick={() => $bulkMut.mutate()} disabled={!bulkClassId || !bulkTermId || $bulkMut.isPending}
          class="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:opacity-90">
          {$bulkMut.isPending ? 'Processing…' : 'Confirm'}
        </button>
      </div>
    </div>
  </div>
{/if}

<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { goto } from '$app/navigation';
  import { listStudents, assignStudentToClass, type StudentSummary } from '$lib/api/students';
  import { listYears } from '$lib/api/academic';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';

  interface Props { classId: string; capacity: number | null; }
  const { classId, capacity }: Props = $props();

  const qc = useQueryClient();

  const studentsQ = createQuery({
    queryKey: ['students', 'class', classId],
    queryFn:  () => listStudents({ class_id: classId, active_only: true }),
    staleTime: 60_000,
  });

  const students     = $derived($studentsQ.data ?? []);
  const occupancy    = $derived(capacity != null ? Math.round((students.length / capacity) * 100) : null);
  const overCapacity = $derived(capacity != null && students.length > capacity);

  // ── Assign student ────────────────────────────────────────────────────────────
  let showAssign    = $state(false);
  let assignYearId  = $state('');
  let assignSearch  = $state('');
  let assignStudentId = $state('');
  let assignError   = $state('');

  // Always fetch years — small dataset, cached 5 min
  const yearsQ = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });

  // Search query uses a writable store so options update reactively without the function form
  const searchOpts = writable({ queryKey: ['students', 'search', ''] as const, queryFn: () => listStudents({ active_only: true, search: '', limit: 30 }), enabled: false, staleTime: 30_000 });
  $effect(() => {
    const s = assignSearch; const active = showAssign && s.trim().length >= 2;
    searchOpts.set({ queryKey: ['students', 'search', s] as const, queryFn: () => listStudents({ active_only: true, search: s, limit: 30 }), enabled: active, staleTime: 30_000 });
  });
  const searchQ = createQuery(searchOpts);

  const assignedIds     = $derived(new Set(students.map(s => s.id)));
  const searchResults   = $derived(($searchQ.data ?? []).filter(s => !assignedIds.has(s.id)));
  const selectedStudent = $derived(($searchQ.data ?? []).find(s => s.id === assignStudentId) ?? null);

  // Default to current year once yearsQ loads
  $effect(() => {
    if (assignYearId) return;
    const cur = ($yearsQ.data ?? []).find(y => y.is_current);
    if (cur) assignYearId = cur.id;
  });

  const assignMut = createMutation({
    mutationFn: () => assignStudentToClass({ student_id: assignStudentId, class_id: classId, academic_year_id: assignYearId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['students', 'class', classId] });
      showAssign = false; assignYearId = ''; assignSearch = ''; assignStudentId = ''; assignError = '';
      toast.success('Student assigned to class.');
    },
    onError: (e) => { assignError = apiError(e, 'Failed to assign student.'); },
  });

  function resetForm() { showAssign = false; assignYearId = ''; assignSearch = ''; assignStudentId = ''; assignError = ''; }

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

<!-- Capacity bar -->
{#if capacity != null && !$studentsQ.isPending}
  <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-3">
    <div class="flex items-center justify-between text-xs">
      <span class="font-medium text-[var(--fg)]">{students.length} / {capacity} students</span>
      <span class="{overCapacity ? 'font-semibold text-red-500' : 'text-[var(--fg-subtle)]'}">
        {overCapacity ? 'Over capacity' : `${occupancy}% full`}
      </span>
    </div>
    <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
      <div class="h-full rounded-full transition-all duration-300"
           style="width:{Math.min(occupancy ?? 0, 100)}%; background:{overCapacity ? '#ef4444' : 'var(--brand)'}"></div>
    </div>
  </div>
{/if}

{#if $studentsQ.isPending}
  <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else}
  <!-- Student list -->
  {#if students.length > 0}
    <div class="mb-4 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">{students.length} student{students.length !== 1 ? 's' : ''}</p>
        <button onclick={() => showAssign = !showAssign}
          class="flex items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Assign student
        </button>
      </div>
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
            <th class="px-4 py-2.5">Name</th>
            <th class="hidden px-4 py-2.5 sm:table-cell">Admission #</th>
            <th class="hidden px-4 py-2.5 sm:table-cell">Gender</th>
            <th class="hidden px-4 py-2.5 md:table-cell">Boarding</th>
          </tr>
        </thead>
        <tbody>
          {#each students as s (s.id)}
            <tr onclick={() => goto(`/students/${s.id}`)}
              class="cursor-pointer border-b border-[var(--border)] last:border-0 transition hover:bg-[var(--hover)]">
              <td class="px-4 py-3">
                <p class="font-medium text-[var(--fg)]">{s.display_name}</p>
                <p class="font-mono text-[10px] text-[var(--fg-subtle)] sm:hidden">{s.admission_number}</p>
              </td>
              <td class="hidden px-4 py-3 font-mono text-xs text-[var(--fg-muted)] sm:table-cell">{s.admission_number}</td>
              <td class="hidden px-4 py-3 sm:table-cell">
                {#if s.gender}
                  <span class="text-xs font-medium {s.gender === 'MALE' ? 'text-blue-600 dark:text-blue-400' : 'text-pink-600 dark:text-pink-400'}">{s.gender}</span>
                {:else}
                  <span class="text-[var(--fg-subtle)]">—</span>
                {/if}
              </td>
              <td class="hidden px-4 py-3 md:table-cell">
                {#if s.is_boarding}
                  <span class="rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-semibold text-purple-700 dark:bg-purple-950/30 dark:text-purple-400">Boarding</span>
                {:else}
                  <span class="text-xs text-[var(--fg-subtle)]">Day</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="mb-4 rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
      <svg class="mx-auto mb-3 h-9 w-9 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>
      </svg>
      <p class="text-sm font-medium text-[var(--fg-muted)]">No students assigned to this class yet.</p>
      <button onclick={() => showAssign = true}
        class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white hover:opacity-90 transition"
        style="background: var(--brand)">Assign first student</button>
    </div>
  {/if}

  <!-- Assign student form -->
  {#if showAssign}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      <p class="text-xs font-semibold text-[var(--fg)]">Assign student to class</p>

      <!-- Academic year -->
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Academic year *</label>
        <select bind:value={assignYearId} class={sel}>
          <option value="">Select year…</option>
          {#each $yearsQ.data ?? [] as y (y.id)}
            <option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>
          {/each}
        </select>
      </div>

      <!-- Student search -->
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Student *</label>
        {#if selectedStudent}
          <!-- Show selected student with a clear button -->
          <div class="flex items-center justify-between rounded-xl border border-[var(--brand)] bg-[var(--hover)] px-3 py-2">
            <div>
              <p class="text-sm font-medium text-[var(--fg)]">{selectedStudent.display_name}</p>
              <p class="font-mono text-[10px] text-[var(--fg-muted)]">{selectedStudent.admission_number}</p>
            </div>
            <button onclick={() => { assignStudentId = ''; assignSearch = ''; }}
              class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Clear</button>
          </div>
        {:else}
          <input bind:value={assignSearch} placeholder="Type at least 2 characters to search…"
            class={sel} />
          {#if assignSearch.trim().length >= 2}
            {#if $searchQ.isPending}
              <p class="mt-1 text-xs text-[var(--fg-subtle)]">Searching…</p>
            {:else if searchResults.length === 0}
              <p class="mt-1 text-xs text-[var(--fg-subtle)]">No students found{assignSearch ? ` matching "${assignSearch}"` : ''}.</p>
            {:else}
              <div class="mt-1 max-h-40 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg)]">
                {#each searchResults as s (s.id)}
                  <button onclick={() => { assignStudentId = s.id; assignSearch = s.display_name; }}
                    class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-[var(--hover)]">
                    <div class="min-w-0 flex-1">
                      <p class="text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
                      <p class="font-mono text-[10px] text-[var(--fg-muted)]">{s.admission_number}{s.current_class_name ? ` · currently in ${s.current_class_name}` : ''}</p>
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
          {/if}
        {/if}
      </div>

      {#if assignError}<p class="text-xs text-red-500">{assignError}</p>{/if}
      <div class="flex gap-2">
        <button
          onclick={() => { assignError = ''; if (!assignYearId) { assignError = 'Select an academic year.'; return; } if (!assignStudentId) { assignError = 'Select a student.'; return; } $assignMut.mutate(); }}
          disabled={$assignMut.isPending}
          class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition"
          style="background:var(--brand)">{$assignMut.isPending ? 'Assigning…' : 'Assign'}</button>
        <button onclick={resetForm}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
      </div>
    </div>
  {/if}
{/if}

<script lang="ts">
  import { createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { getCurrentYear } from '$lib/api/academic';
  import { findCurrentTerm } from '$lib/academicPeriod';
  import { listStudents } from '$lib/api/students';
  import NotRegisteredBanner from '$lib/components/NotRegisteredBanner.svelte';
  import AssignStudentsPanel from './AssignStudentsPanel.svelte';

  interface Props { classId: string; capacity: number | null; classActive: boolean; }
  const { classId, capacity, classActive }: Props = $props();

  const qc = useQueryClient();

  const studentsQ = createQuery({
    queryKey: ['students', 'class', classId],
    queryFn:  () => listStudents({ class_id: classId, active_only: true }),
    staleTime: 60_000,
  });

  const students     = $derived($studentsQ.data ?? []);
  const assignedIds  = $derived(new Set(students.map(s => s.id)));
  const occupancy    = $derived(capacity != null ? Math.round((students.length / capacity) * 100) : null);
  const overCapacity = $derived(capacity != null && students.length > capacity);

  // ── Term registration status ─────────────────────────────────────────────────
  // Folds what used to be a separate "Term Registration" tab into this one —
  // it's fundamentally just a status of the same class roster shown here.
  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const currentTerm = $derived(findCurrentTerm($yearQ.data?.terms ?? []) ?? null);

  const termRosterQ = createQuery({
    queryKey: ['students', 'class', classId, 'term', currentTerm?.id ?? ''],
    queryFn:  () => listStudents({ class_id: classId, active_only: true, term_id: currentTerm!.id }),
    enabled:  !!currentTerm,
    staleTime: 30_000,
  });
  const registeredIds = $derived(new Set(($termRosterQ.data ?? []).map(s => s.id)));
  const notRegistered = $derived(currentTerm ? students.filter(s => !registeredIds.has(s.id)) : []);

  let showAssign = $state(false);

  const COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#ec4899','#14b8a6','#f97316'];
  function avatarBg(name: string): string {
    let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) & 0xff;
    return COLORS[h % COLORS.length];
  }
  function initials(name: string): string {
    const p = name.trim().split(/\s+/);
    return (p[0][0] + (p[1]?.[0] ?? '')).toUpperCase();
  }
</script>

{#if $studentsQ.isPending}
  <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else}
  {#if students.length > 0}
    <div class="mb-4 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <!-- Header: capacity bar + assign button -->
      <div class="flex items-center gap-4 border-b border-[var(--border)] px-4 py-3">
        <div class="flex min-w-0 flex-1 items-center gap-3">
          <p class="shrink-0 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
            {students.length}{capacity != null ? ` / ${capacity}` : ''} students
          </p>
          {#if capacity != null}
            <div class="flex min-w-0 flex-1 items-center gap-2">
              <div class="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--border)]">
                <div class="h-full rounded-full transition-all duration-300"
                     style="width:{Math.min(occupancy ?? 0, 100)}%; background:{overCapacity ? '#ef4444' : 'var(--brand)'}"></div>
              </div>
              <span class="shrink-0 text-[10px] {overCapacity ? 'font-semibold text-red-500' : 'text-[var(--fg-subtle)]'}">
                {overCapacity ? 'Over capacity' : `${occupancy}%`}
              </span>
            </div>
          {/if}
        </div>
        {#if currentTerm && notRegistered.length > 0}
          <NotRegisteredBanner
            items={notRegistered.map(s => ({ student_id: s.id, academic_term_id: currentTerm!.id }))}
            termName={currentTerm.name}
            onRegistered={() => qc.invalidateQueries({ queryKey: ['students', 'class', classId] })}
          />
        {/if}
        {#if classActive}
          <button onclick={() => showAssign = !showAssign}
            class="flex shrink-0 items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
            </svg>
            Assign
          </button>
        {:else}
          <span class="shrink-0 text-[10px] font-semibold text-[var(--fg-subtle)]">Class inactive — reactivate to assign students</span>
        {/if}
      </div>

      <!-- Roster -->
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] bg-[var(--hover)]/30 text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
            <th class="px-4 py-2.5">Student</th>
            <th class="px-4 py-2.5">Term</th>
            <th class="hidden px-4 py-2.5 sm:table-cell">Admission #</th>
            <th class="hidden px-4 py-2.5 sm:table-cell">Gender</th>
            <th class="hidden px-4 py-2.5 md:table-cell">Boarding</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each students as s (s.id)}
            <tr onclick={() => goto(`/students/${s.id}`)} class="cursor-pointer transition hover:bg-[var(--hover)]">
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-2.5">
                  <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
                       style="background: {avatarBg(s.display_name)}">{initials(s.display_name)}</div>
                  <div class="min-w-0">
                    <p class="truncate font-medium text-[var(--fg)]">{s.display_name}</p>
                    <p class="font-mono text-[10px] text-[var(--fg-subtle)] sm:hidden">{s.admission_number}</p>
                  </div>
                </div>
              </td>
              <td class="px-4 py-2.5">
                {#if !currentTerm}
                  <span class="text-xs text-[var(--fg-subtle)]">—</span>
                {:else if registeredIds.has(s.id)}
                  <span class="text-xs font-medium text-green-600 dark:text-green-400">✓ Registered</span>
                {:else}
                  <span class="text-xs text-[var(--fg-subtle)]">Not registered</span>
                {/if}
              </td>
              <td class="hidden px-4 py-2.5 font-mono text-xs text-[var(--fg-muted)] sm:table-cell">{s.admission_number}</td>
              <td class="hidden px-4 py-2.5 sm:table-cell">
                {#if s.gender}
                  <span class="text-xs font-semibold {s.gender === 'MALE' ? 'text-blue-600 dark:text-blue-400' : 'text-pink-600 dark:text-pink-400'}">{s.gender}</span>
                {:else}<span class="text-[var(--fg-subtle)]">—</span>{/if}
              </td>
              <td class="hidden px-4 py-2.5 md:table-cell">
                {#if s.is_boarding}
                  <span class="rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-semibold text-purple-700 dark:bg-purple-950/30 dark:text-purple-400">Boarding</span>
                {:else}<span class="text-xs text-[var(--fg-subtle)]">Day</span>{/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

  {:else}
    <div class="mb-4 rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
      <svg class="mx-auto mb-3 h-9 w-9 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
      </svg>
      <p class="text-sm font-medium text-[var(--fg-muted)]">No students assigned yet{capacity ? ` · Capacity: ${capacity}` : ''}.</p>
      {#if classActive}
        <button onclick={() => showAssign = true}
          class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background: var(--brand)">Assign students</button>
      {:else}
        <p class="mt-3 text-xs text-[var(--fg-subtle)]">This class is inactive — reactivate it before assigning students.</p>
      {/if}
    </div>
  {/if}

  {#if showAssign && classActive}
    <AssignStudentsPanel {classId} {assignedIds} onClose={() => showAssign = false} />
  {/if}
{/if}

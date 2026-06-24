<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { listStudents } from '$lib/api/students';

  interface Props { classId: string; capacity: number | null; }
  const { classId, capacity }: Props = $props();

  const studentsQ = createQuery({
    queryKey: ['students', 'class', classId],
    queryFn:  () => listStudents({ class_id: classId, active_only: true }),
    staleTime: 60_000,
  });

  const students    = $derived($studentsQ.data ?? []);
  const occupancy   = $derived(capacity != null ? Math.round((students.length / capacity) * 100) : null);
  const overCapacity = $derived(capacity != null && students.length > capacity);
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
{:else if students.length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
    <svg class="mx-auto mb-3 h-9 w-9 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>
    </svg>
    <p class="text-sm font-medium text-[var(--fg-muted)]">No active students in this class</p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Students are enrolled from their profile page.</p>
  </div>
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <div class="border-b border-[var(--border)] px-4 py-2.5">
      <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">{students.length} student{students.length !== 1 ? 's' : ''}</p>
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
  <p class="mt-2 text-xs text-[var(--fg-subtle)]">Click any student to open their profile. Enroll students from their profile → Enrollment tab.</p>
{/if}

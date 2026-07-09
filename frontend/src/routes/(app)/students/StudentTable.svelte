<script lang="ts">
  import { goto } from '$app/navigation';
  import type { StudentSummary } from '$lib/api/students';

  type SortCol = 'name' | 'admission' | 'class';

  interface Props {
    students:    StudentSummary[];
    selected:    Set<string>;
    allSelected: boolean;
    isAdmin:     boolean;
    sortCol:     SortCol;
    sortDir:     'asc' | 'desc';
    onSort:      (col: SortCol) => void;
    onToggle:    (id: string) => void;
    onToggleAll: () => void;
  }
  const { students, selected, allSelected, isAdmin, sortCol, sortDir, onSort, onToggle, onToggleAll }: Props = $props();

  function initials(s: StudentSummary) {
    return (s.first_name[0] + s.last_name[0]).toUpperCase();
  }

  function genderBadge(g: string | null) {
    if (g === 'MALE')   return 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300';
    if (g === 'FEMALE') return 'bg-pink-100 text-pink-700 dark:bg-pink-950/40 dark:text-pink-300';
    return 'hidden';
  }

  const thBtn = 'flex items-center gap-0.5 text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)] transition hover:text-[var(--fg)]';
</script>

{#snippet chevron(col: SortCol)}
  <svg class="h-3 w-3 shrink-0 {sortCol === col ? 'opacity-100' : 'opacity-0'}"
       fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
    {#if sortDir === 'asc'}
      <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5"/>
    {:else}
      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
    {/if}
  </svg>
{/snippet}

<div class="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <table class="w-full text-sm">
    <thead class="sticky top-0 z-10">
      <tr class="border-b border-[var(--border)] bg-[var(--hover)]">
        {#if isAdmin}
          <th class="w-10 px-4 py-3">
            <input type="checkbox" checked={allSelected} onchange={onToggleAll}
                   class="rounded accent-[var(--brand)]" />
          </th>
        {/if}
        <th class="px-4 py-3 text-left">
          <button onclick={() => onSort('name')} class={thBtn}>Student {@render chevron('name')}</button>
        </th>
        <th class="hidden px-4 py-3 text-left sm:table-cell">
          <button onclick={() => onSort('admission')} class={thBtn}>Admission No. {@render chevron('admission')}</button>
        </th>
        <th class="hidden px-4 py-3 text-left md:table-cell">
          <button onclick={() => onSort('class')} class={thBtn}>Class {@render chevron('class')}</button>
        </th>
        <th class="hidden px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)] lg:table-cell">Gender</th>
        <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Status</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-[var(--border)]">
      {#each students as s (s.id)}
        {@const rowSelected = selected.has(s.id)}
        <tr onclick={() => goto(`/students/${s.id}`)}
            class="cursor-pointer transition hover:bg-[var(--hover)]
                   {rowSelected ? '!bg-[color-mix(in_srgb,var(--brand)_6%,transparent)]' : ''}">
          {#if isAdmin}
            <td class="w-10 px-4 py-3" onclick={(e) => { e.stopPropagation(); onToggle(s.id); }}>
              <input type="checkbox" checked={rowSelected} onchange={() => onToggle(s.id)}
                     class="rounded accent-[var(--brand)]" />
            </td>
          {/if}
          <td class="px-4 py-3">
            <div class="flex items-center gap-3">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                   style="background: var(--brand)">{initials(s)}</div>
              <div>
                <p class="font-medium text-[var(--fg)]">{s.display_name}</p>
                <div class="flex flex-wrap items-center gap-1 sm:hidden">
                  <span class="font-mono text-xs text-[var(--fg-muted)]">{s.admission_number}</span>
                  {#if s.current_class_name}
                    <span class="text-xs text-[var(--fg-subtle)]">· {s.current_class_name}</span>
                  {/if}
                </div>
              </div>
            </div>
          </td>
          <td class="hidden px-4 py-3 font-mono text-xs text-[var(--fg-muted)] sm:table-cell">{s.admission_number}</td>
          <td class="hidden px-4 py-3 md:table-cell">
            {#if s.current_class_name}
              <span class="rounded-lg bg-[var(--hover)] px-2 py-0.5 text-xs font-medium text-[var(--fg)]">{s.current_class_name}</span>
            {:else}
              <span class="text-xs text-[var(--fg-subtle)]">Not enrolled</span>
            {/if}
          </td>
          <td class="hidden px-4 py-3 lg:table-cell">
            {#if s.gender}
              <span class="inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold uppercase {genderBadge(s.gender)}">{s.gender}</span>
            {:else}
              <span class="text-xs text-[var(--fg-subtle)]">—</span>
            {/if}
          </td>
          <td class="px-4 py-3">
            <div class="flex flex-wrap gap-1">
              {#if s.is_active}
                <span class="inline-flex items-center gap-1 text-[10px] font-bold text-green-600 dark:text-green-500">
                  <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>Active
                </span>
              {:else}
                <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--fg-muted)]">Inactive</span>
              {/if}
              {#if s.is_boarding}
                <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700
                             ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400">Boarding</span>
              {/if}
            </div>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

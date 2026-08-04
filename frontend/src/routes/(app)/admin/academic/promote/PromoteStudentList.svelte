<script lang="ts">
  import type { StudentSummary } from '$lib/api/students';

  // Extracted out of +page.svelte (was pushing the file over the 300-line
  // cap) — the checkbox roster for the source class, no promotion logic of
  // its own.
  interface Props {
    students: StudentSummary[];
    selected: Set<string>;
    alreadyProcessed?: Set<string>;
    onToggleOne: (id: string) => void;
    onToggleAll: () => void;
    onClear: () => void;
  }
  const { students, selected, alreadyProcessed = new Set(), onToggleOne, onToggleAll, onClear }: Props = $props();

  const allSelected = $derived(students.length > 0 && selected.size === students.length);
</script>

<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <!-- List header -->
  <div class="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
    <label class="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-[var(--fg)]">
      <input type="checkbox" checked={allSelected} onchange={onToggleAll} class="h-4 w-4 rounded accent-[var(--brand)]" />
      {selected.size > 0 ? `${selected.size} of ${students.length} selected` : `${students.length} students`}
    </label>
    {#if selected.size > 0}
      <button onclick={onClear} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
        Clear selection
      </button>
    {/if}
  </div>

  {#each students as s (s.id)}
    <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-0
                   transition hover:bg-[var(--hover)] {selected.has(s.id) ? 'bg-[var(--brand)]/5' : ''}">
      <input type="checkbox" checked={selected.has(s.id)} onchange={() => onToggleOne(s.id)}
        class="h-4 w-4 shrink-0 rounded accent-[var(--brand)]" />
      <div class="flex-1 min-w-0">
        <p class="text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
        <p class="text-[10px] font-mono text-[var(--fg-subtle)]">{s.admission_number}</p>
      </div>
      {#if alreadyProcessed.has(s.id)}
        <span class="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-400">
          Already processed
        </span>
      {/if}
      <span class="shrink-0 text-[10px] font-medium
                    {s.gender === 'MALE' ? 'text-blue-600 dark:text-blue-400' : 'text-pink-600 dark:text-pink-400'}">
        {s.gender ?? '—'}
      </span>
    </label>
  {/each}
</div>

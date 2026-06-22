<script lang="ts">
  import type { Assessment, Score } from '$lib/api/assessments';

  interface Props {
    assessment: Assessment;
    students: { id: string; display_name: string; admission_number: string }[];
    scoreMap: Map<string, Score>;
    canEnterScores: boolean;
    scoreInputs: Record<string, string>;
    isPending: boolean;
    onSave: () => void;
  }
  let {
    assessment: a, students, scoreMap, canEnterScores,
    scoreInputs = $bindable(), isPending, onSave,
  }: Props = $props();
</script>

<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-3">Student</th>
        <th class="px-4 py-3 text-center">Score / {a.max_score}</th>
        <th class="hidden px-4 py-3 text-center sm:table-cell">Grade</th>
        <th class="px-4 py-3 text-center">Status</th>
      </tr>
    </thead>
    <tbody>
      {#each students as student (student.id)}
        {@const existing   = scoreMap.get(student.id)}
        {@const val        = scoreInputs[student.id]}
        {@const outOfRange = val !== undefined && val !== '' && (parseFloat(val) < 0 || parseFloat(val) > Number(a.max_score))}
        <tr class="border-b border-[var(--border)] last:border-0 {outOfRange ? 'bg-red-50 dark:bg-red-950/20' : ''}">
          <td class="px-4 py-2.5">
            <p class="font-medium text-[var(--fg)]">{student.display_name}</p>
            <p class="text-[10px] font-mono text-[var(--fg-subtle)]">{student.admission_number}</p>
          </td>
          <td class="px-4 py-2.5 text-center">
            {#if a.is_published}
              <span class="font-mono text-[var(--fg)]">{existing?.raw_score ?? '—'}</span>
            {:else if canEnterScores}
              <input type="number" min="0" max={a.max_score} step="0.5"
                bind:value={scoreInputs[student.id]} placeholder="—"
                class="w-20 rounded-lg border px-2 py-1 text-center text-sm font-mono text-[var(--fg)] focus:outline-none transition
                  {outOfRange ? 'border-red-400 bg-red-50 dark:bg-red-950/30' : 'border-[var(--border)] bg-[var(--bg)] focus:border-[var(--brand)]'}" />
            {:else}
              <span class="font-mono text-[var(--fg-muted)]">{existing?.raw_score ?? '—'}</span>
            {/if}
          </td>
          <td class="hidden px-4 py-2.5 text-center sm:table-cell">
            {#if existing?.cached_grade_label}
              <span class="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400">
                {existing.cached_grade_label}
              </span>
            {:else}
              <span class="text-[var(--fg-subtle)]">—</span>
            {/if}
          </td>
          <td class="px-4 py-2.5 text-center">
            {#if outOfRange}
              <span class="text-[10px] font-semibold text-red-500">Out of range</span>
            {:else if !existing}
              <span class="text-[10px] text-[var(--fg-subtle)]">Not entered</span>
            {:else if existing.is_approved}
              <svg class="mx-auto h-4 w-4 text-green-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
            {:else}
              <span class="text-[10px] text-amber-600 dark:text-amber-400">Pending</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
{#if canEnterScores && !a.is_published}
  <div class="mt-3 flex justify-end">
    <button onclick={onSave} disabled={isPending}
      class="rounded-xl px-5 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
      {isPending ? 'Saving…' : 'Save scores'}
    </button>
  </div>
{/if}

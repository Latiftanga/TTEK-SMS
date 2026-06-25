<script lang="ts">
  import type { Assessment, Score } from '$lib/api/assessments';

  interface StudentRow { id: string; display_name: string; admission_number: string; }

  interface Props {
    assessment: Assessment;
    students: StudentRow[];
    scoreMap: Map<string, Score>;
    scoreInputs: Record<string, string | number>;
    canEnterScores: boolean;
    isPending: boolean;
    onSave: () => void;
  }
  let {
    assessment: a, students, scoreMap, canEnterScores,
    scoreInputs = $bindable(), isPending, onSave,
  }: Props = $props();

  // ── Progress / stats ──────────────────────────────────────────────────────────
  const enteredCount = $derived(
    students.filter(s => scoreInputs[s.id] != null && scoreInputs[s.id] !== '').length
  );
  const progress = $derived(students.length > 0 ? Math.round((enteredCount / students.length) * 100) : 0);

  const hasUnsaved = $derived.by(() => {
    for (const s of students) {
      const existing = scoreMap.get(s.id);
      const raw = scoreInputs[s.id];
      const inputNum = (raw === '' || raw == null) ? null : Number(raw);
      const savedNum = existing !== undefined ? Number(existing.raw_score) : null;
      if (inputNum !== savedNum) return true;
    }
    return false;
  });

  const rawScores = $derived(
    [...scoreMap.values()].map(s => Number(s.raw_score)).filter(v => !isNaN(v))
  );
  const classAvg  = $derived(rawScores.length ? rawScores.reduce((a, b) => a + b, 0) / rawScores.length : null);
  const classHigh = $derived(rawScores.length ? Math.max(...rawScores) : null);
  const classLow  = $derived(rawScores.length ? Math.min(...rawScores) : null);

  // ── Keyboard navigation ───────────────────────────────────────────────────────
  function handleKeydown(e: KeyboardEvent, idx: number) {
    if (e.key === 'Enter' || e.key === 'ArrowDown') {
      e.preventDefault();
      (document.querySelector(`[data-score-idx="${idx + 1}"]`) as HTMLInputElement | null)?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      (document.querySelector(`[data-score-idx="${idx - 1}"]`) as HTMLInputElement | null)?.focus();
    }
  }

  function gradeColor(label: string): string {
    const l = label.toUpperCase();
    if (l === 'A1' || l === 'A') return 'bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/30 dark:text-green-400';
    if (l.startsWith('B')) return 'bg-blue-50 text-blue-700 ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400';
    if (l.startsWith('C')) return 'bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400';
    return 'bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950/30 dark:text-red-400';
  }
</script>

<!-- Progress header (only while entering) -->
{#if !a.is_published && canEnterScores && students.length > 0}
  <div class="mb-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-3">
    <div class="flex items-center justify-between text-xs">
      <span class="font-medium text-[var(--fg)]">{enteredCount} / {students.length} scores entered</span>
      {#if hasUnsaved}
        <span class="font-semibold text-amber-600 dark:text-amber-400">Unsaved changes</span>
      {:else if enteredCount > 0}
        <span class="text-green-600 dark:text-green-400">All saved</span>
      {/if}
    </div>
    <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
      <div class="h-full rounded-full transition-all duration-300"
           style="width:{progress}%; background:var(--brand)"></div>
    </div>
  </div>
{/if}

<!-- Published stats -->
{#if a.is_published && rawScores.length > 0}
  <div class="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-center">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Entries</p>
      <p class="mt-1 text-xl font-bold text-[var(--fg)]">{rawScores.length}<span class="text-sm font-normal text-[var(--fg-muted)]">/{students.length}</span></p>
    </div>
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-center">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Average</p>
      <p class="mt-1 text-xl font-bold text-[var(--fg)]">{classAvg !== null ? classAvg.toFixed(1) : '—'}</p>
    </div>
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-center">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Highest</p>
      <p class="mt-1 text-xl font-bold text-green-600 dark:text-green-400">{classHigh ?? '—'}</p>
    </div>
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-center">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Lowest</p>
      <p class="mt-1 text-xl font-bold text-red-500 dark:text-red-400">{classLow ?? '—'}</p>
    </div>
  </div>
{/if}

<!-- Score table -->
<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <!-- Mobile hint -->
  {#if !a.is_published && canEnterScores}
    <p class="border-b border-[var(--border)] px-4 py-2 text-[10px] text-[var(--fg-subtle)]">
      Tip: press Enter or ↓ to move to the next student
    </p>
  {/if}

  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-3">Student</th>
        <th class="px-4 py-3 text-center">Score<span class="hidden sm:inline"> / {a.max_score}</span></th>
        <th class="px-4 py-3 text-center">Grade</th>
        <th class="px-4 py-3 text-center">Status</th>
      </tr>
    </thead>
    <tbody>
      {#each students as student, idx (student.id)}
        {@const existing   = scoreMap.get(student.id)}
        {@const val        = scoreInputs[student.id]}
        {@const numVal     = Number(val)}
        {@const outOfRange = val != null && val !== '' && (isNaN(numVal) || numVal < 0 || numVal > Number(a.max_score))}
        <tr class="border-b border-[var(--border)] last:border-0 transition
                   {outOfRange ? 'bg-red-50 dark:bg-red-950/20' : 'hover:bg-[var(--hover)]/50'}">
          <td class="px-4 py-3">
            <p class="font-medium text-[var(--fg)]">{student.display_name}</p>
            <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{student.admission_number}</p>
          </td>
          <td class="px-4 py-3 text-center">
            {#if a.is_published}
              <span class="font-mono font-semibold text-[var(--fg)]">{existing?.raw_score ?? '—'}</span>
            {:else if canEnterScores}
              <input
                type="number" min="0" max={a.max_score} step="0.5"
                bind:value={scoreInputs[student.id]}
                placeholder="—"
                data-score-idx={idx}
                onkeydown={(e) => handleKeydown(e, idx)}
                class="w-20 rounded-xl border px-2 py-2 text-center font-mono text-sm text-[var(--fg)]
                       focus:outline-none focus:ring-2 transition sm:w-24
                       {outOfRange
                         ? 'border-red-400 bg-red-50 focus:ring-red-300 dark:bg-red-950/30'
                         : 'border-[var(--border)] bg-[var(--bg)] focus:border-[var(--brand)] focus:ring-[var(--brand)]/20'}" />
            {:else}
              <span class="font-mono text-[var(--fg-muted)]">{existing?.raw_score ?? '—'}</span>
            {/if}
          </td>
          <td class="px-4 py-3 text-center">
            {#if existing?.cached_grade_label}
              <span class="inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold ring-1 ring-inset {gradeColor(existing.cached_grade_label)}">
                {existing.cached_grade_label}
              </span>
            {:else}
              <span class="text-[var(--fg-subtle)]">—</span>
            {/if}
          </td>
          <td class="px-4 py-3 text-center">
            {#if outOfRange}
              <span class="inline-block rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-600 dark:bg-red-950/30 dark:text-red-400">Range!</span>
            {:else if !existing}
              <span class="text-[10px] text-[var(--fg-subtle)]">—</span>
            {:else if existing.is_approved}
              <span class="inline-flex items-center gap-1 text-[10px] font-semibold text-green-600 dark:text-green-400">
                <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                Approved
              </span>
            {:else}
              <span class="text-[10px] font-medium text-amber-600 dark:text-amber-400">Pending</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<!-- Save button -->
{#if canEnterScores && !a.is_published}
  <div class="mt-3 flex items-center justify-between">
    <p class="text-xs {hasUnsaved ? 'font-medium text-amber-600 dark:text-amber-400' : 'text-[var(--fg-subtle)]'}">
      {hasUnsaved ? 'You have unsaved changes' : enteredCount > 0 ? 'All scores saved' : ''}
    </p>
    <button onclick={onSave} disabled={isPending || !hasUnsaved}
      class="rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
      style="background: var(--brand)">
      {isPending ? 'Saving…' : 'Save scores'}
    </button>
  </div>
{/if}

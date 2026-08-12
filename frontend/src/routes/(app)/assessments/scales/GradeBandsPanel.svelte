<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addGrade, deleteGrade, type Grade } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';

  interface Props { scaleId: string; grades: Grade[]; isShared: boolean; }
  const { scaleId, grades, isShared }: Props = $props();

  const qc = useQueryClient();
  let showAddForm = $state(false);

  const sortedGrades = $derived(
    [...grades].sort((a, b) => Number(b.min_score) - Number(a.min_score))
  );

  const addMut = createMutation({
    mutationFn: () => addGrade(scaleId, {
      min_score: parseFloat(bandForm.min_score),
      max_score: parseFloat(bandForm.max_score),
      letter_grade: bandForm.letter_grade.trim(),
      label: bandForm.label.trim(),
      gpa_points: bandForm.gpa_points ? parseFloat(bandForm.gpa_points) : null,
      remarks: bandForm.remarks.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      showAddForm = false; bandError = '';
      bandForm = { min_score: '', max_score: '', letter_grade: '', label: '', gpa_points: '', remarks: '' };
      toast.success('Grade band added.');
    },
    onError: (e: unknown) => {
      bandError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not add grade.';
    },
  });

  const deleteMut = createMutation({
    mutationFn: (gradeId: string) => deleteGrade(scaleId, gradeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      toast.success('Grade band removed.');
    },
    onError: () => toast.error('Could not remove grade band.'),
  });

  let bandForm = $state({ min_score: '', max_score: '', letter_grade: '', label: '', gpa_points: '', remarks: '' });
  let bandError = $state('');

  function handleAddBand() {
    bandError = '';
    const min = parseFloat(bandForm.min_score), max = parseFloat(bandForm.max_score);
    if (isNaN(min) || isNaN(max)) { bandError = 'Enter valid min/max scores.'; return; }
    if (min > max)                 { bandError = 'Min must be ≤ max.'; return; }
    if (!bandForm.letter_grade.trim()) { bandError = 'Letter grade is required.'; return; }
    if (!bandForm.label.trim())        { bandError = 'Label is required.'; return; }
    $addMut.mutate();
  }
</script>

{#if sortedGrades.length > 0}
  <div class="overflow-x-auto overflow-y-hidden rounded-xl border border-[var(--border)]">
    <table class="w-full text-xs">
      <thead><tr class="border-b border-[var(--border)] text-left text-[9px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-3 py-2">Range</th>
        <th class="px-3 py-2">Grade</th>
        <th class="px-3 py-2">Label</th>
        <th class="hidden px-3 py-2 sm:table-cell">GPA</th>
        {#if !isShared}<th class="px-3 py-2"></th>{/if}
      </tr></thead>
      <tbody>
        {#each sortedGrades as g (g.id)}
          <tr class="border-b border-[var(--border)] last:border-0">
            <td class="px-3 py-2 font-mono text-[var(--fg-muted)]">{g.min_score}–{g.max_score}</td>
            <td class="px-3 py-2 font-bold text-[var(--fg)]">{g.letter_grade}</td>
            <td class="px-3 py-2 text-[var(--fg-muted)]">{g.label}</td>
            <td class="hidden px-3 py-2 font-mono text-[var(--fg-subtle)] sm:table-cell">{g.gpa_points ?? '—'}</td>
            {#if !isShared}
              <td class="px-3 py-2 text-right">
                <button onclick={() => $deleteMut.mutate(g.id)} disabled={$deleteMut.isPending}
                  class="rounded p-0.5 text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-30">
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                </button>
              </td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{:else}
  <p class="text-xs text-[var(--fg-muted)]">No grade bands defined yet.</p>
{/if}

<!-- Add band form -->
{#if !isShared && showAddForm}
  <div class="rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3 space-y-2.5">
    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <div><label class="label-xs">Min</label><input type="number" step="0.5" bind:value={bandForm.min_score} placeholder="50" class="inp" /></div>
      <div><label class="label-xs">Max</label><input type="number" step="0.5" bind:value={bandForm.max_score} placeholder="69" class="inp" /></div>
      <div><label class="label-xs">Letter</label><input bind:value={bandForm.letter_grade} placeholder="B" class="inp" /></div>
      <div><label class="label-xs">Label</label><input bind:value={bandForm.label} placeholder="Good" class="inp" /></div>
      <div><label class="label-xs">GPA</label><input type="number" step="0.01" bind:value={bandForm.gpa_points} placeholder="—" class="inp" /></div>
      <div class="col-span-2 sm:col-span-3"><label class="label-xs">Remarks</label><input bind:value={bandForm.remarks} placeholder="Optional" class="inp" /></div>
    </div>
    {#if bandError}<p class="text-xs text-red-500">{bandError}</p>{/if}
    <div class="flex gap-2">
      <button onclick={handleAddBand} disabled={$addMut.isPending}
        class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$addMut.isPending ? 'Adding…' : 'Add band'}
      </button>
      <button onclick={() => { showAddForm = false; bandError = ''; }}
        class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
    </div>
  </div>
{:else if !isShared}
  <button onclick={() => showAddForm = true}
    class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">
    + Add grade band
  </button>
{/if}

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-[10px] font-medium text-[var(--fg-muted)] mb-0.5; }
  .inp { @apply w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

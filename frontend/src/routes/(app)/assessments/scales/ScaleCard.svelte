<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addGrade, deleteGrade, type GradingScale, type Grade } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';

  interface Props { scale: GradingScale; }
  const { scale }: Props = $props();

  const qc = useQueryClient();
  let expanded   = $state(false);
  let showAddForm = $state(false);
  let form = $state({ min_score: '', max_score: '', letter_grade: '', label: '', gpa_points: '', remarks: '' });
  let formError = $state('');

  const sortedGrades = $derived(
    [...scale.grades].sort((a, b) => Number(b.min_score) - Number(a.min_score))
  );

  const addMut = createMutation({
    mutationFn: () => addGrade(scale.id, {
      min_score: parseFloat(form.min_score),
      max_score: parseFloat(form.max_score),
      letter_grade: form.letter_grade.trim(),
      label: form.label.trim(),
      gpa_points: form.gpa_points ? parseFloat(form.gpa_points) : null,
      remarks: form.remarks.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      showAddForm = false; formError = '';
      form = { min_score: '', max_score: '', letter_grade: '', label: '', gpa_points: '', remarks: '' };
      toast.success('Grade band added.');
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not add grade.';
    },
  });

  const deleteMut = createMutation({
    mutationFn: (gradeId: string) => deleteGrade(scale.id, gradeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      toast.success('Grade band removed.');
    },
    onError: () => toast.error('Could not remove grade band.'),
  });

  function handleAdd() {
    formError = '';
    const min = parseFloat(form.min_score), max = parseFloat(form.max_score);
    if (isNaN(min) || isNaN(max)) { formError = 'Enter valid min/max scores.'; return; }
    if (min > max)                 { formError = 'Min must be ≤ max.'; return; }
    if (!form.letter_grade.trim()) { formError = 'Letter grade is required.'; return; }
    if (!form.label.trim())        { formError = 'Label is required.'; return; }
    $addMut.mutate();
  }
</script>

<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <!-- Header -->
  <button onclick={() => expanded = !expanded}
    class="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-[var(--hover)]">
    <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform duration-200 {expanded ? 'rotate-90' : ''}"
      fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
    <span class="flex-1 font-semibold text-[var(--fg)]">{scale.name}</span>
    {#if scale.is_default}
      <span class="shrink-0 rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400">Default</span>
    {/if}
    <span class="shrink-0 text-xs text-[var(--fg-subtle)]">{scale.grades.length} bands</span>
  </button>

  {#if expanded}
    <div class="border-t border-[var(--border)] px-5 pb-4 pt-3 space-y-3">

      <!-- Grade bands table -->
      {#if sortedGrades.length > 0}
        <div class="overflow-hidden rounded-xl border border-[var(--border)]">
          <table class="w-full text-xs">
            <thead><tr class="border-b border-[var(--border)] text-left text-[9px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
              <th class="px-3 py-2">Range</th>
              <th class="px-3 py-2">Grade</th>
              <th class="px-3 py-2">Label</th>
              <th class="hidden px-3 py-2 sm:table-cell">GPA</th>
              <th class="px-3 py-2"></th>
            </tr></thead>
            <tbody>
              {#each sortedGrades as g (g.id)}
                <tr class="border-b border-[var(--border)] last:border-0">
                  <td class="px-3 py-2 font-mono text-[var(--fg-muted)]">{g.min_score}–{g.max_score}</td>
                  <td class="px-3 py-2 font-bold text-[var(--fg)]">{g.letter_grade}</td>
                  <td class="px-3 py-2 text-[var(--fg-muted)]">{g.label}</td>
                  <td class="hidden px-3 py-2 font-mono text-[var(--fg-subtle)] sm:table-cell">{g.gpa_points ?? '—'}</td>
                  <td class="px-3 py-2 text-right">
                    <button onclick={() => $deleteMut.mutate(g.id)} disabled={$deleteMut.isPending}
                      class="rounded p-0.5 text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-30">
                      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                      </svg>
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <p class="text-xs text-[var(--fg-muted)]">No grade bands defined yet.</p>
      {/if}

      <!-- Add band form -->
      {#if showAddForm}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3 space-y-2.5">
          <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div><label class="label-xs">Min score</label><input type="number" step="0.5" bind:value={form.min_score} placeholder="50" class="inp" /></div>
            <div><label class="label-xs">Max score</label><input type="number" step="0.5" bind:value={form.max_score} placeholder="69" class="inp" /></div>
            <div><label class="label-xs">Letter</label><input bind:value={form.letter_grade} placeholder="B" class="inp" /></div>
            <div><label class="label-xs">Label</label><input bind:value={form.label} placeholder="Good" class="inp" /></div>
            <div><label class="label-xs">GPA</label><input type="number" step="0.01" bind:value={form.gpa_points} placeholder="—" class="inp" /></div>
            <div class="col-span-2 sm:col-span-3"><label class="label-xs">Remarks</label><input bind:value={form.remarks} placeholder="Optional" class="inp" /></div>
          </div>
          {#if formError}<p class="text-xs text-red-500">{formError}</p>{/if}
          <div class="flex gap-2">
            <button onclick={handleAdd} disabled={$addMut.isPending}
              class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
              {$addMut.isPending ? 'Adding…' : 'Add band'}
            </button>
            <button onclick={() => { showAddForm = false; formError = ''; }}
              class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
          </div>
        </div>
      {:else}
        <button onclick={() => showAddForm = true}
          class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">
          + Add grade band
        </button>
      {/if}

    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-[10px] font-medium text-[var(--fg-muted)] mb-0.5; }
  .inp { @apply w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addGrade, deleteGrade, updateGradingScale, type GradingScale } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';

  interface Props { scale: GradingScale; }
  const { scale }: Props = $props();

  const qc = useQueryClient();
  let expanded    = $state(false);
  let showAddForm = $state(false);
  let editing     = $state(false);

  let editForm = $state({ name: scale.name, description: scale.description ?? '' });
  let editError = $state('');

  const sortedGrades = $derived(
    [...scale.grades].sort((a, b) => Number(b.min_score) - Number(a.min_score))
  );

  // A shared system-default scale (school_id=NULL, seeded — see
  // services/grading.py::resolve_grade) is read-only here: every edit/delete
  // endpoint already requires an exact school_id match, so it can't be
  // reached through this UI regardless — a school overrides it by creating
  // and defaulting their own scale instead.
  const isShared = $derived(scale.school_id === null);

  // ── Mutations ─────────────────────────────────────────────────────────────────

  const updateMut = createMutation({
    mutationFn: (data: { name?: string; description?: string; is_default?: boolean }) =>
      updateGradingScale(scale.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      editing = false; editError = '';
      toast.success('Grading scale updated.');
    },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.';
    },
  });

  const addMut = createMutation({
    mutationFn: () => addGrade(scale.id, {
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
    mutationFn: (gradeId: string) => deleteGrade(scale.id, gradeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      toast.success('Grade band removed.');
    },
    onError: () => toast.error('Could not remove grade band.'),
  });

  // ── Grade band form state ─────────────────────────────────────────────────────

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

  function startEdit() {
    editForm = { name: scale.name, description: scale.description ?? '' };
    editError = '';
    editing = true;
  }

  function handleSaveEdit() {
    editError = '';
    if (!editForm.name.trim()) { editError = 'Name is required.'; return; }
    $updateMut.mutate({ name: editForm.name.trim(), description: editForm.description.trim() || undefined });
  }

  function handleSetDefault() {
    $updateMut.mutate({ is_default: true });
  }
</script>

<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <!-- Header row -->
  <div class="flex items-center gap-2 px-4 py-3.5">
    <button onclick={() => expanded = !expanded}
      class="flex flex-1 items-center gap-2.5 min-w-0 text-left">
      <svg class="h-3.5 w-3.5 shrink-0 text-[var(--fg-muted)] transition-transform duration-200 {expanded ? 'rotate-90' : ''}"
        fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
      <span class="truncate font-semibold text-[var(--fg)]">{scale.name}</span>
      {#if scale.description}
        <span class="hidden truncate text-xs text-[var(--fg-subtle)] sm:inline">{scale.description}</span>
      {/if}
    </button>

    <!-- Badges + actions -->
    <div class="flex shrink-0 items-center gap-2">
      {#if isShared}
        <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--fg-muted)] ring-1 ring-inset ring-[var(--border)]" title="Applies to every school until they create their own">System default</span>
      {:else if scale.is_default}
        <span class="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400">Default</span>
      {:else}
        <button
          onclick={handleSetDefault}
          disabled={$updateMut.isPending}
          class="rounded-full border border-[var(--border)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)] transition hover:border-blue-400 hover:text-blue-600 disabled:opacity-40 dark:hover:border-blue-500 dark:hover:text-blue-400"
          title="Set as default grading scale">
          {$updateMut.isPending ? '…' : 'Set default'}
        </button>
      {/if}
      <span class="text-xs text-[var(--fg-subtle)]">{scale.grades.length} bands</span>
      <!-- Edit button -->
      {#if !isShared}
        <button onclick={startEdit}
          class="rounded-lg p-1 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]"
          title="Edit scale">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
          </svg>
        </button>
      {/if}
    </div>
  </div>

  <!-- Edit form -->
  {#if editing}
    <div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 pb-4 pt-3 space-y-2.5">
      <div class="grid gap-2 sm:grid-cols-2">
        <div>
          <label class="label-xs">Scale name <span class="text-red-500">*</span></label>
          <input bind:value={editForm.name} placeholder="e.g. Standard Grading Scale" class="inp" />
        </div>
        <div>
          <label class="label-xs">Description</label>
          <input bind:value={editForm.description} placeholder="Optional" class="inp" />
        </div>
      </div>
      {#if editError}<p class="text-xs text-red-500">{editError}</p>{/if}
      <div class="flex gap-2">
        <button onclick={handleSaveEdit} disabled={$updateMut.isPending}
          class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
          style="background: var(--brand)">
          {$updateMut.isPending ? 'Saving…' : 'Save'}
        </button>
        <button onclick={() => { editing = false; editError = ''; }}
          class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
      </div>
    </div>
  {/if}

  <!-- Grade bands (expanded) -->
  {#if expanded}
    <div class="border-t border-[var(--border)] px-4 pb-4 pt-3 space-y-3">

      {#if sortedGrades.length > 0}
        <div class="overflow-hidden rounded-xl border border-[var(--border)]">
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

    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-[10px] font-medium text-[var(--fg-muted)] mb-0.5; }
  .inp { @apply w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

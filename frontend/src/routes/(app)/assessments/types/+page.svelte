<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listAssessmentTypes, createAssessmentType, updateAssessmentType,
    type AssessmentType,
  } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';

  const qc = useQueryClient();
  setPageTitle('Assessment Types');

  const typesQ = createQuery({
    queryKey: ['assessment-types'],
    queryFn:  listAssessmentTypes,
    staleTime: 5 * 60_000,
  });

  const totalWeight = $derived(
    ($typesQ.data ?? []).reduce((sum, t) => sum + Number(t.weight), 0)
  );
  const weightOk = $derived(Math.abs(totalWeight - 100) < 0.01);

  // ── Create form ───────────────────────────────────────────────────────────────
  let showForm  = $state(false);
  let form = $state({ name: '', code: '', weight: '' });
  let formError = $state('');

  const createMut = createMutation({
    mutationFn: () => createAssessmentType({
      name: form.name.trim(),
      code: form.code.trim().toUpperCase(),
      weight: parseFloat(form.weight),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessment-types'] });
      showForm = false; formError = '';
      form = { name: '', code: '', weight: '' };
      toast.success('Assessment type created.');
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create.';
    },
  });

  function handleCreate() {
    formError = '';
    if (!form.name.trim()) { formError = 'Name is required.'; return; }
    if (!form.code.trim()) { formError = 'Code is required.'; return; }
    const w = parseFloat(form.weight);
    if (isNaN(w) || w <= 0 || w > 100) { formError = 'Weight must be between 0.01 and 100.'; return; }
    $createMut.mutate();
  }

  // ── Inline edit ───────────────────────────────────────────────────────────────
  let editingId  = $state<string | null>(null);
  let editForm   = $state({ name: '', code: '', weight: '' });
  let editError  = $state('');

  function startEdit(t: AssessmentType) {
    editingId = t.id;
    editForm  = { name: t.name, code: t.code, weight: String(t.weight) };
    editError = '';
    showForm  = false;
  }

  const updateMut = createMutation({
    mutationFn: (id: string) => updateAssessmentType(id, {
      name:   editForm.name.trim(),
      code:   editForm.code.trim().toUpperCase(),
      weight: parseFloat(editForm.weight),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessment-types'] });
      editingId = null; editError = '';
      toast.success('Assessment type updated.');
    },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.';
    },
  });

  function handleUpdate(id: string) {
    editError = '';
    if (!editForm.name.trim()) { editError = 'Name is required.'; return; }
    if (!editForm.code.trim()) { editError = 'Code is required.'; return; }
    const w = parseFloat(editForm.weight);
    if (isNaN(w) || w <= 0 || w > 100) { editError = 'Weight must be between 0.01 and 100.'; return; }
    $updateMut.mutate(id);
  }
</script>

<!-- Header -->
<div class="mb-4 flex flex-wrap items-start justify-between gap-3">
  <div>
    <p class="text-sm font-semibold text-[var(--fg)]">Assessment Types</p>
    <p class="text-xs text-[var(--fg-muted)]">
      Define categories of assessment. Weights are percentages — they should sum to 100.
    </p>
  </div>
  <div class="flex items-center gap-2">
    {#if ($typesQ.data ?? []).length > 0}
      <span class="rounded-full px-2.5 py-0.5 text-[10px] font-bold ring-1 ring-inset
        {weightOk
          ? 'bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/30 dark:text-green-400'
          : 'bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400'}">
        Total: {totalWeight.toFixed(2)}%{weightOk ? ' ✓' : ' ≠ 100'}
      </span>
    {/if}
    <button onclick={() => { showForm = !showForm; formError = ''; editingId = null; }}
      class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add type
    </button>
  </div>
</div>

{#if showForm}
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <div class="grid gap-3 sm:grid-cols-3">
      <div><label for="at-name" class="label">Name <span class="text-red-500">*</span></label><input id="at-name" bind:value={form.name} placeholder="End of Term" class="input" /></div>
      <div><label for="at-code" class="label">Code <span class="text-red-500">*</span></label><input id="at-code" bind:value={form.code} placeholder="EOT" class="input" /></div>
      <div><label for="at-weight" class="label">Weight % <span class="text-red-500">*</span></label><input id="at-weight" type="number" min="0.01" max="100" step="0.01" bind:value={form.weight} placeholder="e.g. 70" class="input" /></div>
    </div>
    {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={handleCreate} disabled={$createMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$createMut.isPending ? 'Creating…' : 'Create'}
      </button>
      <button onclick={() => { showForm = false; formError = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
    </div>
  </div>
{/if}

{#if $typesQ.isPending}
  <div class="space-y-2">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if ($typesQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No assessment types defined yet.</p>
  </div>
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <table class="w-full text-sm">
      <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-3">Name</th>
        <th class="px-4 py-3">Code</th>
        <th class="px-4 py-3 text-right">Weight</th>
        <th class="px-4 py-3">Status</th>
        <th class="px-4 py-3"></th>
      </tr></thead>
      <tbody>
        {#each $typesQ.data ?? [] as t (t.id)}
          <tr class="border-b border-[var(--border)] last:border-0">
            <td class="px-4 py-3 font-medium text-[var(--fg)]">{t.name}</td>
            <td class="px-4 py-3 font-mono text-[var(--fg-muted)]">{t.code}</td>
            <td class="px-4 py-3 text-right font-mono text-[var(--fg-muted)]">{Number(t.weight).toFixed(2)}%</td>
            <td class="px-4 py-3">
              {#if t.is_active}
                <span class="text-xs font-semibold text-green-600 dark:text-green-500">Active</span>
              {:else}
                <span class="text-xs text-[var(--fg-subtle)]">Inactive</span>
              {/if}
            </td>
            <td class="px-4 py-3 text-right">
              <button onclick={() => editingId === t.id ? (editingId = null) : startEdit(t)}
                class="rounded-lg p-1 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]"
                title="Edit">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
                </svg>
              </button>
            </td>
          </tr>
          {#if editingId === t.id}
            <tr class="border-b border-[var(--border)] last:border-0 bg-[var(--bg)]">
              <td colspan="5" class="px-4 pb-4 pt-2">
                <div class="grid gap-2 sm:grid-cols-3">
                  <div><label class="label-xs">Name <span class="text-red-500">*</span></label><input bind:value={editForm.name} class="inp" /></div>
                  <div><label class="label-xs">Code <span class="text-red-500">*</span></label><input bind:value={editForm.code} class="inp" /></div>
                  <div><label class="label-xs">Weight % <span class="text-red-500">*</span></label><input type="number" min="0.01" max="100" step="0.01" bind:value={editForm.weight} class="inp" /></div>
                </div>
                {#if editError}<p class="mt-1.5 text-xs text-red-500">{editError}</p>{/if}
                <div class="mt-2 flex gap-2">
                  <button onclick={() => handleUpdate(t.id)} disabled={$updateMut.isPending}
                    class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
                    {$updateMut.isPending ? 'Saving…' : 'Save'}
                  </button>
                  <button onclick={() => { editingId = null; editError = ''; }}
                    class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label    { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .label-xs { @apply block text-[10px] font-medium text-[var(--fg-muted)] mb-0.5; }
  .input    { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
  .inp      { @apply w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

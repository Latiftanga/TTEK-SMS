<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listAssessmentTypes, createAssessmentType, type AssessmentType } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';

  const qc = useQueryClient();

  const typesQ = createQuery({
    queryKey: ['assessment-types'],
    queryFn:  listAssessmentTypes,
    staleTime: 5 * 60_000,
  });

  let showForm = $state(false);
  let form = $state({ name: '', code: '', weight: '1' });
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
      form = { name: '', code: '', weight: '1' };
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
    if (isNaN(w) || w <= 0) { formError = 'Weight must be a positive number.'; return; }
    $createMut.mutate();
  }
</script>

<div class="flex items-center justify-between mb-4">
  <div>
    <p class="text-sm font-semibold text-[var(--fg)]">Assessment Types</p>
    <p class="text-xs text-[var(--fg-muted)]">Define the categories of assessment used by your school (e.g. Classwork, Mid-term, End of term).</p>
  </div>
  <button onclick={() => { showForm = !showForm; formError = ''; }}
    class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 shrink-0"
    style="background: var(--brand)">
    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
    Add type
  </button>
</div>

{#if showForm}
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <div class="grid gap-3 sm:grid-cols-3">
      <div class="sm:col-span-1"><label for="at-name" class="label">Name <span class="text-red-500">*</span></label><input id="at-name" bind:value={form.name} placeholder="End of Term" class="input" /></div>
      <div><label for="at-code" class="label">Code <span class="text-red-500">*</span></label><input id="at-code" bind:value={form.code} placeholder="EOT" class="input" /></div>
      <div><label for="at-weight" class="label">Weight <span class="text-red-500">*</span></label><input id="at-weight" type="number" min="0.01" step="0.01" bind:value={form.weight} class="input" /></div>
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
      </tr></thead>
      <tbody>
        {#each $typesQ.data ?? [] as t (t.id)}
          <tr class="border-b border-[var(--border)] last:border-0">
            <td class="px-4 py-3 font-medium text-[var(--fg)]">{t.name}</td>
            <td class="px-4 py-3 font-mono text-[var(--fg-muted)]">{t.code}</td>
            <td class="px-4 py-3 text-right font-mono text-[var(--fg-muted)]">{t.weight}</td>
            <td class="px-4 py-3">
              {#if t.is_active}
                <span class="text-xs font-semibold text-green-600 dark:text-green-500">Active</span>
              {:else}
                <span class="text-xs text-[var(--fg-subtle)]">Inactive</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

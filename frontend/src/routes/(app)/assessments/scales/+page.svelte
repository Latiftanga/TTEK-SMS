<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listGradingScales, createGradingScale } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';
  import ScaleCard from './ScaleCard.svelte';

  const qc = useQueryClient();

  const scalesQ = createQuery({
    queryKey: ['grading-scales'],
    queryFn:  listGradingScales,
    staleTime: 5 * 60_000,
  });

  let showForm  = $state(false);
  let form = $state({ name: '', description: '', is_default: false });
  let formError = $state('');

  const createMut = createMutation({
    mutationFn: () => createGradingScale({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      is_default: form.is_default,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      showForm = false; formError = '';
      form = { name: '', description: '', is_default: false };
      toast.success('Grading scale created.');
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create.';
    },
  });

  function handleCreate() {
    formError = '';
    if (!form.name.trim()) { formError = 'Name is required.'; return; }
    $createMut.mutate();
  }
</script>

<div class="flex items-center justify-between mb-4">
  <div>
    <p class="text-sm font-semibold text-[var(--fg)]">Grading Scales</p>
    <p class="text-xs text-[var(--fg-muted)]">Define letter grade bands. The default scale is used when approving scores.</p>
  </div>
  <button onclick={() => { showForm = !showForm; formError = ''; }}
    class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 shrink-0"
    style="background: var(--brand)">
    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
    New scale
  </button>
</div>

{#if showForm}
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
    <div class="grid gap-3 sm:grid-cols-2">
      <div><label for="gs-name" class="label">Scale name <span class="text-red-500">*</span></label><input id="gs-name" bind:value={form.name} placeholder="Ghana GES Standard" class="input" /></div>
      <div><label for="gs-desc" class="label">Description</label><input id="gs-desc" bind:value={form.description} placeholder="Optional" class="input" /></div>
    </div>
    <div class="flex items-center gap-2">
      <input type="checkbox" id="gs-default" bind:checked={form.is_default} class="accent-[var(--brand)]" />
      <label for="gs-default" class="text-sm text-[var(--fg)]">Set as default scale</label>
    </div>
    {#if formError}<p class="text-xs text-red-500">{formError}</p>{/if}
    <div class="flex gap-2">
      <button onclick={handleCreate} disabled={$createMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$createMut.isPending ? 'Creating…' : 'Create scale'}
      </button>
      <button onclick={() => { showForm = false; formError = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
    </div>
  </div>
{/if}

{#if $scalesQ.isPending}
  <div class="space-y-2">{#each [1,2] as _}<div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>
{:else if ($scalesQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No grading scales defined.</p>
    <p class="mt-1 text-xs text-[var(--fg-subtle)]">Create a scale and add grade bands to enable score grading.</p>
  </div>
{:else}
  <div class="space-y-2">
    {#each $scalesQ.data ?? [] as scale (scale.id)}
      <ScaleCard {scale} />
    {/each}
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>

<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    listCurriculumUnits, updateCurriculumUnit, type CurriculumUnit, type CurriculumUnitUpdatePayload,
  } from '$lib/api/curriculumUnits';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';

  interface Props { materialId: string; }
  const { materialId }: Props = $props();

  const unitsQ = reactiveQuery(() => ({
    queryKey: ['curriculum-units', materialId] as const,
    queryFn: () => listCurriculumUnits(materialId),
    staleTime: 30_000,
  }));
  const units = $derived($unitsQ.data ?? []);

  let editingId = $state<string | null>(null);
  let draft = $state<CurriculumUnitUpdatePayload>({});

  const qc = useQueryClient();
  const saveMut = createMutation({
    mutationFn: (vars: { id: string; data: CurriculumUnitUpdatePayload }) => updateCurriculumUnit(vars.id, vars.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['curriculum-units', materialId] });
      editingId = null;
      toast.success('Corrected.');
    },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not save this correction.')),
  });

  function startEdit(u: CurriculumUnit) {
    editingId = u.id;
    draft = {
      unit_label: u.unit_label, strand: u.strand, sub_strand: u.sub_strand,
      content_standard: u.content_standard, indicator: u.indicator,
      learning_objectives: u.learning_objectives, topics: u.topics,
    };
  }
</script>

{#if $unitsQ.isPending}
  <div class="h-16 animate-pulse rounded-xl bg-[var(--hover)]"></div>
{:else if units.length === 0}
  <p class="py-3 text-center text-xs text-[var(--fg-subtle)]">
    No structured units extracted yet — extraction accuracy on a long document is
    unverified, so review each one below once it runs.
  </p>
{:else}
  <div class="space-y-2">
    {#each units as u (u.id)}
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
        {#if editingId === u.id}
          <div class="space-y-2">
            <input bind:value={draft.unit_label} placeholder="Unit label (e.g. Week 3)"
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)]" />
            <div class="grid gap-2 sm:grid-cols-2">
              <input bind:value={draft.strand} placeholder="Strand"
                class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)]" />
              <input bind:value={draft.sub_strand} placeholder="Sub-strand"
                class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)]" />
            </div>
            <textarea bind:value={draft.content_standard} placeholder="Content standard" rows="2"
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)]"></textarea>
            <textarea bind:value={draft.indicator} placeholder="Indicator" rows="2"
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)]"></textarea>
            <textarea bind:value={draft.topics} placeholder="Topics / focal area" rows="2"
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)]"></textarea>
            <div class="flex gap-2">
              <button onclick={() => $saveMut.mutate({ id: u.id, data: draft })} disabled={$saveMut.isPending}
                class="min-h-[36px] rounded-lg px-3 text-xs font-semibold text-white disabled:opacity-50" style="background: var(--brand)">
                {$saveMut.isPending ? 'Saving…' : 'Save correction'}
              </button>
              <button onclick={() => editingId = null}
                class="min-h-[36px] rounded-lg border border-[var(--border)] px-3 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)]">
                Cancel
              </button>
            </div>
          </div>
        {:else}
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="text-xs font-semibold text-[var(--fg)]">{u.unit_label ?? `Unit ${u.sequence_number}`}</p>
              {#if u.strand}<p class="mt-0.5 text-[11px] text-[var(--fg-muted)]">{u.strand}{u.sub_strand ? ` — ${u.sub_strand}` : ''}</p>{/if}
              {#if u.content_standard}<p class="mt-1 text-[11px] text-[var(--fg)]">{u.content_standard}</p>{/if}
              <p class="mt-1 text-[10px] text-[var(--fg-subtle)]">Pages {u.source_page_start}–{u.source_page_end}</p>
            </div>
            <button onclick={() => startEdit(u)}
              class="min-h-[36px] shrink-0 rounded-lg border border-[var(--border)] px-2.5 text-[11px] font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)]">
              Correct
            </button>
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
